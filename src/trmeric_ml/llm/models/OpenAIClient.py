import os
import tiktoken
import traceback
import threading
from openai import OpenAI
from dotenv import load_dotenv
from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.LLMLogger import log_llm_response
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions,ModelOptions2, MODEL_REGISTRY,OpenAIParamBuilder
from src.trmeric_ml.llm.utils.reinforcement import _optimize_prompt
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
from src.trmeric_services.reinforcement import core, engine, feedback, policy
import time


load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")


class ChatGPTClient(LLMClient):
    def __init__(self, user_id=None, tenant_id=None):
        super().__init__("chatgpt", user_id=user_id, tenant_id=tenant_id)
        self.openai = OpenAI(api_key=os.getenv("OPENAI_KEY"))
        self.rl = core.ReinforcementLearning()
        self.policy_optimizer = policy.PolicyOptimizer()
        self.user_id = user_id
        self.tenant_id = tenant_id

    def run_rl(
        self,
        chat: ChatCompletion = None,
        options: ModelOptions = None,
        agent_name: str = None,
        function_name: str = None,
        logInDb: dict = None,
        streaming: bool = False,
        **kwargs
    ):
        """
        Execute LLM with RL-optimized prompt and parameters.
        """
        try:
            socketio = kwargs.get("socketio", None)
            client_id = kwargs.get("client_id", None)
            timer_id = super().run(chat, options, function_name, logInDb)
            
            #Naming convention for function
            # section::subsection::feature_name
            feature_name = function_name.split("::")[-1]
            section = function_name.split("::")[0] 
            if section not in ["roadmap_scope","roadmap_solution"]:
                section = None
            subsection = function_name.split("::")[1] if len(function_name.split("::"))>2 else None

            print("--debug section subsection feature_name-----",section,subsection,feature_name)

            tenant_id = logInDb.get("tenant_id") if logInDb else self.tenant_id
            user_id = logInDb.get('user_id') if logInDb else self.user_id

            # Get optimized parameters
            print("--debug PARAMS BEFORE-----",options,options.model,options.max_tokens,options.temperature)
            optimized_options = self.policy_optimizer.get_optimized_params(tenant_id, agent_name, feature_name, options,section=section,subsection=subsection, user_id=user_id)
            print("--debug OPTIMIZED PARAMS-----",optimized_options,optimized_options.model,optimized_options.max_tokens,optimized_options.temperature)
            
            # Format chat messages with dynamic prompt injection in **User Prompt**
            formatted_chat = chat.format()
            user_prompt = _optimize_prompt(
                raw_prompt=formatted_chat["user"],
                tenant_id=tenant_id,
                agent_name=agent_name,
                feature_name=feature_name,
                section = section,
                subsection = subsection,
                streaming = streaming,
                user_id = user_id,
            )
            
            messages = [{"role": "system", "content": formatted_chat["system"]}]
            for message in formatted_chat["prev"]:
                messages.append({"role": "assistant", "content": message["assistant"]})
                messages.append({"role": "user", "content": message["user"]})
            messages.append({"role": "user", "content": user_prompt})
            
            prompt_token_count = self.count_tokens(messages, optimized_options.model)
            print(f"\n\nToken count: {prompt_token_count}, \n--deubg user_prompt-----", user_prompt[-100:])

            completion_token_count = 0
            full_response = ""
            print(f"Running LLM call with streaming: {streaming}")
            response = self.openai.chat.completions.create(
                model=optimized_options.model,
                messages=messages,
                max_tokens=optimized_options.max_tokens,
                temperature=optimized_options.temperature,
                stream= streaming,
            )
            # Run LLM
            if streaming:
                # move the streaming logic into an inner generator function, so the outer function is no longer a generator.
                def stream_generator():
                    full_response = ""
                    completion_token_count = 0
                    counter = 0
                    try:
                        for chunk in response:
                            try:
                                content_chunk = chunk.choices[0].delta.content
                                if content_chunk:
                                    if len(content_chunk) > 100 and content_chunk.isspace():
                                        counter += 1
                                        if counter >= 100:
                                            raise Exception("GPT failed to send proper output: keeps sending spaces")
                                        continue

                                    full_response += content_chunk

                                    try:
                                        enc = tiktoken.encoding_for_model(options.model)
                                    except KeyError:
                                        enc = tiktoken.get_encoding("cl100k_base")
                                    completion_token_count += len(enc.encode(content_chunk))
                                    yield content_chunk
                            except (KeyError, AttributeError, TypeError) as parse_err:
                                self._handle_error(timer_id, parse_err, prompt_token_count, function_name, "stream_chunk", socketio, client_id)
                                continue
                    finally:
                        print("Stream completed")
                        self._log_db_stats(
                            logInDb,
                            function_name,
                            options.model,
                            completion_token_count + prompt_token_count,
                            prompt_token_count,
                            completion_token_count,
                        )

                return stream_generator()
            else: ##### Streaming
                response_content = response.choices[0].message.content
                self._log_db_stats(
                    logInDb,
                    function_name,
                    response.model,
                    response.usage.total_tokens,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
                return response_content

        except Exception as e:
            appLogger.error({"event": "run_RL","error": str(e),"streaming": streaming,"traceback": traceback.format_exc()})
            self._handle_error(timer_id, e, prompt_token_count, function_name, "run_RL",socketio,client_id)
            raise

    # Helper method to enhance system prompt with memory and web search in parallel
    def _enhance_system_prompt(self, chat, memory, web, web_user):
        """Run memory and web enhancements in parallel threads if both are enabled"""
        # if memory is None:
        #     memory = self.user_id

        if not memory and not web:
            return chat

        # Create a copy of the system prompt for thread safety
        original_system = chat.system

        # Results container for thread functions
        results = {"memory_result": None, "web_result": None}

        # Thread functions
        def memory_thread_func():
            if memory:
                results["memory_result"] = self.memoryUpdatedSystemPrompt(original_system, memory)

        def web_thread_func():
            if web:
                results["web_result"] = self.webUpdatedSystemPrompt(original_system, web_user, chat.user)

        # Create and start threads
        threads = []
        if memory:
            memory_thread = threading.Thread(target=memory_thread_func)
            memory_thread.start()
            threads.append(memory_thread)

        if web:
            web_thread = threading.Thread(target=web_thread_func)
            web_thread.start()
            threads.append(web_thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Start with the original system prompt
        enhanced_system = original_system

        # Append memory enhancements if available
        if memory and results["memory_result"]:
            enhanced_system += results["memory_result"]

        # Append web enhancements if available
        if web and results["web_result"]:
            enhanced_system += results["web_result"]

        import random

        random_int = random.randint(0, len(enhanced_system) - 1)
        filename = f"enhanced{random_int}"
        if web and memory and results["memory_result"] and results["web_result"]:
            if not web and not results["web_result"]:
                filename += "memory.txt"
            else:
                filename += ".txt"
            with open(filename, "w") as f:
                f.write(str(enhanced_system))

        # Update the chat with the enhanced system prompt
        chat.system = enhanced_system

        return chat

    # Helper method to prepare messages from chat
    def _prepare_messages(self, chat):
        formatted_chat = chat.format()
        messages = [{"role": "system", "content": formatted_chat["system"]}]
        for message in formatted_chat["prev"]:
            messages.append({"role": "assistant", "content": message["assistant"]})
            messages.append({"role": "user", "content": message["user"]})
        messages.append({"role": "user", "content": formatted_chat["user"]})
        return messages, formatted_chat

    # Helper method for error handling
    def _handle_error(
        self,
        timer_id,
        error,
        prompt_token_count,
        function_name=None,
        function_type="api",
        socketio=None,
        client_id=None
    ):
        log_llm_response(timer_id, f"ERROR: {str(error)}", prompt_token_count, 0, prompt_token_count)
        appLogger.error(
            {
                "event": f"error_in_{function_type}_run",
                "function": function_name,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
        )
        if socketio and client_id:
            socketio.emit("open_ai_error",{"event":"openai_error","error_type":function_type,"error":str(error)},room=client_id)
        
        

    # Helper method for logging stats to database
    def _log_db_stats(
        self,
        logInDb,
        function_name,
        model_name,
        total_tokens,
        prompt_tokens,
        completion_tokens,
    ):
        if logInDb is None:
            print("---debug logInDb not provided!!", logInDb)
            return

        try:
            if not self.tenant_id:
                self.tenant_id = logInDb.get("tenant_id")
            if not self.user_id:
                self.user_id = logInDb.get("user_id")
            res = TangoDao.createEntryInStats(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                function_name=function_name,
                model_name=model_name,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            # print("_log_db_stats res: ", res)
            # return True
        except Exception as e:
            appLogger.error(
                {
                    "event": "error_in_storing_stats",
                    "error": e,
                    "traceback": traceback.format_exc(),
                }
            )
            return False

    def runV2(
        self,
        chat: ChatCompletion,
        options: ModelOptions,
        function_name=None,
        logInDb=None,
        memory=None,
        web=False,
        web_user=False,
    ):
        # Start logging the request and get timer_id
        timer_id = super().run(chat, options, function_name, logInDb)

        # Apply memory and web search enhancements in parallel if needed
        chat = self._enhance_system_prompt(chat, memory, web, web_user)

        # Prepare messages
        messages, _ = self._prepare_messages(chat)

        full_response = ""
        counter = 0

        # Calculate prompt tokens before API call
        prompt_token_count = self.count_tokens(messages, options.model)
        total_completion_tokens = 0

        while True:
            try:
                response = self.openai.chat.completions.create(
                    model=options.model,
                    messages=messages,
                    max_tokens=options.max_tokens,
                    temperature=options.temperature,
                    stream=False,
                )
                partial_content = response.choices[0].message.content

                full_response += partial_content
                total_completion_tokens += response.usage.completion_tokens

                # Check the finish reason
                finish_reason = response.choices[0].finish_reason
                print("finish_reason --- debug ", finish_reason)

                if finish_reason == "stop":
                    # Log the completed response
                    log_llm_response(
                        timer_id,
                        full_response,
                        prompt_token_count,
                        total_completion_tokens,
                        prompt_token_count + total_completion_tokens,
                    )
                    break  # Completed successfully
                elif finish_reason == "length":
                    # Add the latest response to the messages for continuation
                    messages.append({"role": "assistant", "content": partial_content})
                else:
                    # Log the response even if it didn't complete normally
                    log_llm_response(
                        timer_id,
                        full_response,
                        prompt_token_count,
                        total_completion_tokens,
                        prompt_token_count + total_completion_tokens,
                    )
                    break

                # Log stats to database
                if self._log_db_stats(
                    logInDb,
                    function_name,
                    response.model,
                    response.usage.total_tokens,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                ):
                    counter += 1

            except Exception as e:
                self._handle_error(timer_id, e, prompt_token_count, function_name)
                break

        return full_response

    def run(
        self,
        chat: ChatCompletion,
        options: ModelOptions,
        function_name=None,
        logInDb=None,
        memory=None,
        web=False,
        web_user=False,
        socketio=None,
        client_id=None
    ):
        # Start logging the request and get timer_id
        timer_id = super().run(chat, options, function_name, logInDb)

        # Apply memory and web search enhancements in parallel if needed
        # chat = self._enhance_system_prompt(chat, memory, web, web_user)

        # Prepare messages
        messages, _ = self._prepare_messages(chat)

        # Calculate prompt tokens before API call
        prompt_token_count = self.count_tokens(messages, options.model)
        print(f"\n\nToken count: {prompt_token_count} for {function_name}")
        debugLogger.info(f"Running run for {function_name} with prompt tokens - {prompt_token_count}")
        try:
            response = self.openai.chat.completions.create(
                model=options.model,
                messages=messages,
                max_tokens=options.max_tokens,
                temperature=options.temperature,
                stream=False,
            )

            # Log the response with token counts
            log_llm_response(
                timer_id,
                response.choices[0].message.content,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )

            # Log stats to database
            self._log_db_stats(
                logInDb,
                function_name,
                response.model,
                response.usage.total_tokens,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            self._handle_error(timer_id, e, prompt_token_count, function_name,"unexpected_error",socketio,client_id)
            raise e

    def memoryUpdatedSystemPrompt(self, system, userid):
        from src.trmeric_utils.knowledge.TangoMemory import TangoMem

        tm = TangoMem(userid).get_insights()
        if tm == "No Tango Memory found for this user":
            return system
        system_prompt = f"""
        You are given a user's system prompt to an AI agent. Your job is to look at this system prompt and some generated insights about the user.
        Based off of this, you should choose which insights are relevant information to the user and which are not.
        
        If there are relevant insights, you should provide a response that includes the relevant insights in a string format. 
        Many of the insights may be irrelevant, so be sure to only include the relevant ones.
        
        Here are your insights to choose from:
        
        {tm}
        
        Remember your job is not to make a response to the user's system prompt, but to provide the most relevant insights from the list above.
        
        return in a json (ints for the insight ids):
        ```json
        {{
            "insights_ids": [insight1_id, insight2_id, insight3_id]
        }}
        """

        user = f"""
        Here is the system prompt that the user provided to the AI agent:
        {system}.
        Only provide the most relevant insights from the list above.
        """

        response = self.run(
            ChatCompletion(system=system_prompt, user=user, prev=[]),
            ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
            "memory_updated_system_prompt",
            memory=False,
            web=False,
        )

        response = extract_json_after_llm(response)
        insight_ids = response.get("insights_ids", [])
        final_insights = ""
        for insight in tm:
            if insight.get("id") in insight_ids:
                final_insights += insight["type"] + ": " + insight["description"] + "\n\n"

        return "\n\n Here are some potentially helpful user insights :\n\n" + final_insights

    def webUpdatedSystemPrompt(self, system, web_user, user=None):
        from src.trmeric_services.phoenix.nodes.web_search import WebSearchNode

        system_prompt = """
        You are given a user's system prompt to an AI agent. Your job is to extract relevant questions 
        that could be used for web searching based on this system prompt. Focus on providing industry standards and best practices where possible.
        
        Return your response in a JSON format with a list of search queries.
        
        Example format:
        {
            "web_queries": ["query1", "query2", "query3"]
        }
        """

        user = f"""
        Here is the system prompt that needs web search queries:
        {system}
        """
        if web_user:
            user += f"""
            Additionally, here is the user's message that will follow: 
            {user}
            """
        user += """
        Generate 0-3 specific search queries that would help gather relevant information. 
        If you feel this is a simple query that can be easily answered, you should always add 0 questions. 
        Pay particular attention to the user's message if provided, which will help you decide if 0 questions are appropriate.
        If it doesn't feel explicitly like a question which would be very helpful to search for, add 0 questions.
        Only submit the questions if you are tasked with something that truly requires specific internet knowledge
        """

        response = self.run(
            ChatCompletion(system=system_prompt, user=user, prev=[]),
            ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.1),
            "web_updated_system_prompt",
            memory=False,
            web=False,
        )

        questions = extract_json_after_llm(response)
        if len(questions.get("web_queries", [])) == 0:
            return None
        web_results = WebSearchNode().run_and_format(
            questions.get("web_queries", []),
            " Here are some possibly relevant search results: \n",
        )

        return "\n\nAdditional context from web search:\n" + str(web_results)

    def runWithStreaming(
        self,
        chat: ChatCompletion,
        options: ModelOptions,
        function_name,
        logInDb=None,
        memory=None,
        web=False,
        web_user=False,
        socketio=None,
        client_id=None,
        **kwargs
    ):
        # Start logging the request and get timer_id
        timer_id = super().run(chat, options, function_name, logInDb)

        # Apply memory and web search enhancements in parallel if needed
        chat = self._enhance_system_prompt(chat, memory, web, web_user)

        # Prepare messages
        messages, _ = self._prepare_messages(chat)

        prompt_token_count = self.count_tokens(messages, options.model)
        completion_token_count = 0
        full_response = ""
        
        debugLogger.info(f"Running runWithStreaming with prompt tokens - {prompt_token_count}")

        try:
            stream = self.openai.chat.completions.create(
                model=options.model,
                messages=messages,
                max_completion_tokens=options.max_tokens,
                temperature=options.temperature,
                stream=True,
            )
            counter = 0
            for chunk in stream:
                try:
                    content_chunk = chunk.choices[0].delta.content
                    if content_chunk:
                        if len(content_chunk) > 100 and content_chunk.isspace() :
                            print(f"Skipped large whitespace chunk: length={len(content_chunk)}")
                            counter += 1
                            if counter >= 100:
                                raise Exception(f"GPT failed to send proper output: Keeps sending spaces")
                            continue
                    
                        full_response += content_chunk
                    
                        try:
                            enc = tiktoken.encoding_for_model(options.model)
                        except KeyError:
                            enc = tiktoken.get_encoding("cl100k_base")
                        completion_token_count += len(enc.encode(content_chunk))
                        yield content_chunk
                    # time.sleep(0.001)
                    
                except (KeyError, AttributeError, TypeError) as parse_err:
                    self._handle_error(timer_id, parse_err, prompt_token_count, function_name, "stream_chunk",socketio,client_id)
                    continue  # Skip malformed chunk
                

            print("Stream completed")
            # Log the final complete response after streaming is done
            log_llm_response(
                timer_id,
                full_response,
                prompt_token_count,
                completion_token_count,
                prompt_token_count + completion_token_count,
            )

            # Log stats to database
            self._log_db_stats(
                logInDb,
                function_name,
                options.model,
                completion_token_count + prompt_token_count,
                prompt_token_count,
                completion_token_count,
            )
            
        except Exception as e:
            self._handle_error(timer_id, e, prompt_token_count, function_name, "streaming",socketio,client_id)
            raise e


    def runWithStreamingV2(
        self,
        chat: ChatCompletion,
        options: ModelOptions,
        function_name,
        logInDb=None,
        memory=None,
        web=False,
        web_user=False,
        socketio=None,
        client_id=None,
        max_loops=10,
    ):
        """
        Stream output safely and automatically continue if truncated (handles proper finish_reason).
        """
        print("start --- runWithStreamingV2 ")
        timer_id = super().run(chat, options, function_name, logInDb)
        chat = self._enhance_system_prompt(chat, memory, web, web_user)
        messages, _ = self._prepare_messages(chat)

        prompt_token_count = self.count_tokens(messages, options.model)
        full_response = ""
        full_response = ""
        completion_token_count = 0
        loop = 1

        # 🧠 Memory across loops: tail of previous loop's output
        prev_tail = ""          # last few hundred chars from previous loop
        TAIL_WINDOW = 500       # how much tail to remember

        while loop <= max_loops:
            debugLogger.info(f"runWithStreamingV2 loop {loop} | prompt tokens = {prompt_token_count}")
            finish_reason = None
            partial_response = ""

            try:
                stream = self.openai.chat.completions.create(
                    model=options.model,
                    messages=messages,
                    max_completion_tokens=options.max_tokens,
                    temperature=options.temperature,
                    stream=True,
                )

                # snapshot the tail for this loop (used for first chunks in this loop)
                loop_prev_tail = prev_tail if loop > 1 else ""

                counter = 0
                temp = ''
                found_overalp = False
                clean_temp = True
                first_found = False
                for chunk in stream:
                    # Each chunk has structure: ChatCompletionChunk -> choices[0].delta.content
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    content_chunk = getattr(delta, "content", None)

                    if content_chunk:
                        # Skip huge whitespace floods
                        if len(content_chunk) > 100 and content_chunk.isspace():
                            print(f"Skipped large whitespace chunk: length={len(content_chunk)}")
                            counter += 1
                            if counter >= 100:
                                raise Exception("GPT failed to send proper output: Keeps sending spaces")
                            continue
                        

                        # --------------------------------------------------------------------------
                        # 🔁 Overlap detection (live streaming, stable version)
                        # --------------------------------------------------------------------------
                        MIN_OVERLAP = 40
                        TAIL_WINDOW = 300
                        DEBOUNCE_TOKENS = 5  # how many non-matching chars before considering overlap ended

                        # --------------------------------------------------------------------------
                        # 🔁 Simple, stable overlap trimming (live streaming version)
                        # --------------------------------------------------------------------------
                        
                        def remove_stream_overlap(prev_tail, curr_chunk):
                            prev_tail = prev_tail.strip()
                            curr_chunk = curr_chunk.strip()
                            max_overlap = 0
                            for i in range(1, min(len(prev_tail), len(curr_chunk)) + 1):
                                if prev_tail[-i:].lower() == curr_chunk[:i].lower():
                                    max_overlap = i
                            return curr_chunk[max_overlap:]
                        
                        
                        def remove_stream_overlap(prev_tail, curr_chunk):
                            prev_tail = prev_tail.rstrip()   # keep line integrity
                            curr_chunk = curr_chunk.lstrip()
                            max_overlap = 0
                            for i in range(1, min(len(prev_tail), len(curr_chunk)) + 1):
                                if prev_tail[-i:].lower() == curr_chunk[:i].lower():
                                    max_overlap = i
                            return curr_chunk[max_overlap:]


                        if loop_prev_tail and not first_found:
                            # small buffer to accumulate possible overlap
                            temp += content_chunk
                            tail_slice = loop_prev_tail[-200:]

                            # if temp still matches part of the tail, keep buffering
                            if temp and temp in tail_slice:
                                if len(temp) >= MIN_OVERLAP:
                                    found_overalp = True
                                    print("🟠 Overlap detecting..:", len(temp), "**", temp)
                                continue

                            # if we were buffering overlap and now it diverged → skip the repeated part
                            if found_overalp:
                                found_overalp = False
                                extra_chunk = remove_stream_overlap(tail_slice, temp)
                                print(f"✅ Overlap ended. Fresh content starts with: {extra_chunk}")
                                first_found = True
                                temp = ""  # discard repeated text
                        #         # now yield fresh part
                        #         yield extra_chunk
                        #         partial_response += extra_chunk
                        #         full_response += extra_chunk
                        #     else:
                        #         # it was a false alarm (didn’t cross threshold)
                        #         if temp:
                        #             yield temp
                        #             partial_response += temp
                        #             full_response += temp
                        #             temp = ""
                        #         else:
                        #             partial_response += content_chunk
                        #             full_response += content_chunk
                        #             yield content_chunk
                        # else:
                        #     partial_response += content_chunk
                        #     full_response += content_chunk
                        #     yield content_chunk
                            
                            
                        partial_response += content_chunk
                        full_response += content_chunk
                        yield content_chunk

                    # The last chunk includes finish_reason
                    if choice.finish_reason is not None:
                        finish_reason = choice.finish_reason

                print(f"✅ Stream {loop} completed ({len(full_response)} chars so far) finish_reason={finish_reason}")

                # --- continuation logic ---
                if finish_reason == "stop":
                    # normal completion
                    prev_tail = ""  # reset; no more loops expected
                    break

                elif finish_reason == "length":
                    print("⚠️ Streaming truncated — continuing next loop...")
                    print("all content streamed in this run ")
                    print(partial_response)
                    print("-------")

                    # # ensure clean newline boundary in partial_response
                    # if not partial_response.endswith("\n"):
                    #     partial_response += "\n"
                    #     yield "\n"

                    # 🧠 update cross-loop tail memory ONLY here
                    if partial_response:
                        prev_tail = partial_response[-TAIL_WINDOW:]
                        
                    first_found = False

                    # ✅ Add last output to message history for continuation
                    messages.append({"role": "assistant", "content": partial_response})
                    # messages.append({
                    #     "role": "user",
                    #     "content": (
                    #         """
                    #         You were generating a structured table or list that was cut off because of token limits.

                    #         ⚠️ Continue **exactly** where you left off.
                    #         - Do NOT repeat or reprint any rows, headers, or entries that were already shown.
                    #         - Maintain the **exact same table format** or JSON structure.
                    #         - Continue directly from the **current unfinished item**, no table header again, but repeat the item.
                    #         - Do NOT add any new introductions, explanations, or table headers.
                    #         Only output the remaining continuation in the same structure.
                            
                    #         Also do not print hyphens, or table headers when rendering table when starting new fresh run.
                            
                    #         If rendering table: Continue markdown table from current unfinished row, no table header again, but repeat the item.
                    #         If rendering list: Continue from last valid key/value pair.
                    #         "Continue exactly where you left off, same format and tone, without repeating previous text."
                    #         "Continue markdown table from the next unfinished row. "
                    #         "Do NOT repeat the header or previous rows. Maintain exact same columns."
                    #         "Continue JSON from the next key/value pair. "
                    #         "Do not repeat or reopen previous braces or keys. Only output valid JSON continuation."
                            
                            
                    #         Very important:: Do not abruptly end the answer. Make sure you have properly summarized and given 
                    #         next steps properly
                    #         """
                    #     )
                    # })
                    messages.append({
                        "role": "user",
                        "content": (
                            """
                            You were generating a structured output (table or JSON or list) 
                            that was truncated due to token limits.

                            ⚠️ Continue **exactly where it stopped**, following these rules:

                            - Do **not** repeat or restate any completed rows, keys, or list items.
                            - If the last row or item was **cut off mid-line**, re-emit that single incomplete row **from its start** once (starting with a newline), then continue normally.
                            - For **Markdown tables**:
                                - Do **not** re-emit table headers or divider lines (`| # |`, `|---|`) — those are Markdown table header re-emission artifacts.
                                - Begin immediately with the next unfinished or new table row.
                            - For **lists or JSON**, continue with the next unfinished element.
                            - Keep the same indentation, columns, and tone. Maintain **identical structure, formatting, and style** as before.
                            - Do **not** add explanations, restatements, or summaries at the top.
                            - End cleanly and completely (no abrupt stop).
                            - ⚠️ **Very important:** Do not abruptly end the answer. Ensure it concludes with a clear summary and next steps.

                            """
                        )
                    })


                    loop += 1
                    continue

                else:
                    # if no finish_reason (rare API quirk), but response looks incomplete — fallback check
                    if len(partial_response.strip()) > 50 and not full_response.strip().endswith(("}", "]", "!", ".", "```")):
                        print("⚠️ No finish_reason but likely truncated, continuing anyway.")
                        if partial_response:
                            prev_tail = partial_response[-TAIL_WINDOW:]
                        messages.append({"role": "assistant", "content": partial_response})
                        messages.append({
                            "role": "user",
                            "content": "Continue exactly where you left off without repeating previous text."
                        })
                        loop += 1
                        continue

                    prev_tail = ""  # clean finish
                    break  # otherwise assume complete

            except Exception as e:
                self._handle_error(timer_id, e, prompt_token_count, function_name, "streaming", socketio, client_id)
                raise e

        # --- final logging ---
        log_llm_response(
            timer_id,
            full_response,
            prompt_token_count,
            completion_token_count,
            prompt_token_count + completion_token_count,
        )

        self._log_db_stats(
            logInDb,
            function_name,
            options.model,
            completion_token_count + prompt_token_count,
            prompt_token_count,
            completion_token_count,
        )


    def tokenize(self, text: str, model: str):
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(model)
        return encoding.encode(text)

    def count_tokens(self, messages, model_name):
        try:
            enc = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding for unknown models
            enc = tiktoken.get_encoding("cl100k_base")
        total_tokens = 0
        for message in messages:
            total_tokens += len(enc.encode(message["content"]))
        return total_tokens

    def get_embedding(self, text, model="text-embedding-3-small"):
        text = text.replace("\n", " ")
        return self.openai.embeddings.create(input=[text], model=model).data[0].embedding


    def runVision(
        self,
        system_prompt: str,
        image_base64: str,
        user_instruction: str,
        model: str = "gpt-4.1-mini",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ):
        """
        Run a vision-capable GPT model with an image + instruction.

        This method is for visual understanding ONLY:
        diagrams, architectures, flows, screenshots, charts.
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_instruction
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ],
                },
            ]

            response = self.openai.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return response.choices[0].message.content

        except Exception as e:
            appLogger.error({
                "event": "runVision_error",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            raise


    def exec(self,chat:ChatCompletion,options: ModelOptions2,function_name=None,logInDb=None):
        try:
            spec = MODEL_REGISTRY[options.model]
            messages, _ = self._prepare_messages(chat)
            prompt_token_count = self.count_tokens(messages, options.model)
            # print(f"spec: {spec} \n\nToken count: {prompt_token_count} for {function_name}")

            # if spec.api_type == APIType.CHAT: no need for now
            params = OpenAIParamBuilder.build_chat_params(messages, options)
            response = self.openai.chat.completions.create(**params)
            # print("--debug response exec------", response)

            self._log_db_stats(
                logInDb,
                function_name,
                response.model,
                response.usage.total_tokens,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
            return response.choices[0].message.content
            raise NotImplementedError(f"API type {spec.api_type} not supported yet")

        except Exception as e:
            appLogger.error({'event': 'gptclient_exec','error': str(e),'traceback': traceback.format_exc()})
            self._handle_error(timer_id=None,error=e,prompt_token_count=prompt_token_count,function_name=function_name,function_type="exec")


    def exec_stream(
        self,
        chat: ChatCompletion,
        options: ModelOptions2,
        function_name=None,
        logInDb=None,
        socketio=None,
        client_id=None,
    ):
        """
        Streaming executor for ModelOptions2 (GPT-5.x compatible).
        Supports CHAT api_type for now.
        """
        timer_id = None
        try:
            spec = MODEL_REGISTRY[options.model]


            # Prepare messages
            messages, _ = self._prepare_messages(chat)
            prompt_token_count = self.count_tokens(messages, options.model)
            completion_token_count = 0
            full_response = ""

            # timer_id = super().run(chat, options, function_name, logInDb)

            # Build params using your unified builder
            params = OpenAIParamBuilder.build_chat_params(messages, options)
            params["stream"] = True

            stream = self.openai.chat.completions.create(**params)

            counter = 0
            for chunk in stream:
                try:
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None)

                    if not content:
                        continue

                    # Guard: whitespace flood
                    if len(content) > 100 and content.isspace():
                        counter += 1
                        if counter >= 100:
                            raise Exception("GPT streaming failure: excessive whitespace")
                        continue

                    full_response += content

                    # token estimation (best-effort only)
                    try:
                        enc = tiktoken.encoding_for_model(options.model)
                    except KeyError:
                        enc = tiktoken.get_encoding("cl100k_base")

                    completion_token_count += len(enc.encode(content))

                    # emit to caller
                    yield content

                except Exception as parse_err:
                    print("--parse_err-", parse_err)
                    # self._handle_error(
                    #     timer_id,
                    #     parse_err,
                    #     prompt_token_count,
                    #     function_name,
                    #     "stream_chunk",
                    #     socketio,
                    #     client_id,
                    # )
                    continue

            # # ---- stream finished ----
            # log_llm_response(
            #     timer_id,
            #     full_response,
            #     prompt_token_count,
            #     completion_token_count,
            #     prompt_token_count + completion_token_count,
            # )

            # self._log_db_stats(
            #     logInDb,
            #     function_name,
            #     spec.name,
            #     prompt_token_count + completion_token_count,
            #     prompt_token_count,
            #     completion_token_count,
            # )
            # self._log_db_stats(
            #     logInDb,
            #     function_name,
            #     response.model,
            #     response.usage.total_tokens,
            #     response.usage.prompt_tokens,
            #     response.usage.completion_tokens,
            # )

        except Exception as e:
            appLogger.error(
                {
                    "event": "exec_stream_error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            # self._handle_error(
            #     timer_id,
            #     e,
            #     prompt_token_count if "prompt_token_count" in locals() else 0,
            #     function_name,
            #     "exec_stream",
            #     socketio,
            #     client_id,
            # )
            raise


############first log of gpt-5.1 exec ###############3
# --debug response exec------ ChatCompletion(
# id='chatcmpl-Cspz9phnmVPIoNt0MIxeONhUgPsIy', 
# choices=[Choice(finish_reason='stop', index=0, logprobs=None,
#  message=ChatCompletionMessage(
# content='{\n  "action": "update_resource_data",\n #  "selected_analyze_potential_attributes": {\n    "resource_ids": null,\n    "name": null,\n    "primary_skill": null,\n    "skill_keyword": null,\n    "role": null,\n    "is_external": null,\n    "external_company_name": null,\n    "org_team_name": null,\n    "min_allocation": null,\n    "max_allocation": null,\n    "selected_projection_attrs": [],\n    "portfolio_ids": [],\n    "portfolio_name": null,\n    "country": null\n  },\n #  "unassign_params": [\n    {\n      "resource_name": null,\n      "project_name": null,\n      "roadmap_name": null\n    }\n  ],\n #  "update_resource_params": [\n    {\n      "name": null,\n      "country": null,\n      "role": null,\n      "skills": null,\n      "experience": null,\n      "rate": null,\n      "location": null,\n      "portfolio": null\n    }\n  ],\n #  "assign_params": [\n    {\n      "resource_name": null,\n      "project_name": null,\n      "roadmap_name": null\n    }\n  ],\n#   "clarifying_info": "Which resource(s) do you want to update, and which fields (role, skills, location, etc.) with what new values?",\n #  "thought_process": "User explicitly asked to update resource data but provided no resource name or fields, so set action to update_resource_data and request clarification."\n}',
#  refusal=None, # role='assistant', # annotations=[], # audio=None, # function_call=None,#  tool_calls=None))],#  created=1767185579,
#  model='gpt-5.1-2025-11-13',#  object='chat.completion', # service_tier='default', 
# system_fingerprint=None, # usage=CompletionUsage(# completion_tokens=326, prompt_tokens=2106, total_tokens=2432, 
# completion_tokens_details=CompletionTokensDetails(# accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0),#  prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0)))




#############1st gpt-5.2 log###########################
# --debug response exec------ ChatCompletion(id='chatcmpl-Csq8pvvtQo7GK2VMcEszduePeCMUu',
#  choices=[Choice(finish_reason='stop', index=0, logprobs=None, 
# message=ChatCompletionMessage(content='{\n  "action": "add_potential",\n  "selected_analyze_potential_attributes": {},\n  "unassign_params": [],\n  "update_resource_params": [],\n  "assign_params": [],\n  "clarifying_info": "What would you like to add: (1) a new resource, (2) a new org team, or (3) add an existing resource to an org team? Please share the details (e.g., resource name/email/role/skills/country or org team name).",\n  "thought_process": "User explicitly requested to add potential data but provided no entity type or attributes, so choose add_potential and ask for required details."\n}', refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=None))], created=1767186179, 
# model='gpt-5.2-2025-12-11', object='chat.completion', service_tier='default',
#  system_fingerprint=None,
#  usage=CompletionUsage(completion_tokens=141, prompt_tokens=2106, total_tokens=2247, 
# completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0),
#  prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0)))