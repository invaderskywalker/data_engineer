from src.trmeric_services.agents.core import AgentRegistry, BaseAgent
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_services.agents.prompts import primary_agent_prompt, response_prompt, response_prompt_for_workflow3, response_prompt_of_combined_functions_v3, response_prompt_of_combined_functions_v2
import traceback
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.random import getShortUUID
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_utils.enums import AgentFnTypes
from src.trmeric_api.logging.TimingLogger import start_timer, stop_timer, log_timing

# temp:
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
import json
from src.trmeric_database.dao import KnowledgeDao, TangoDao

AI_INTRO = """
Product Intro 
---------
You are Tango, an AI product of a great company: Trmeric, 
which aims to be an multi agent AI product,
which can understand and guide the user even 
proactively by using their multi-agent system.
"""


class ExecutionManager:
    def __init__(self, agent_registry: AgentRegistry, base_agent: BaseAgent, tangoDataInserter, integrations, log_info=None, socketio=None, client_id=None, **kwargs):
        """Initializes ExecutionManager and registers agents."""
        self.agent_registry = agent_registry
        self.context = {}
        self.steps_executed = []
        self.integrations = integrations
        self.log_info = log_info
        self.base_agent = base_agent
        self.primary_agent: BaseAgent = None
        self.tangoDataInserter = tangoDataInserter
        self.socketio = socketio
        self.client_id = client_id

        # Base logging context for timing calls
        self.log_context = self._create_log_context()

        # temp:
        self.llm = ChatGPTClient(user_id=self.log_info.get("user_id"))

        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=8096,
            temperature=0
        )
        self.modelOptions2 = ModelOptions(
            model="gpt-4.1",
            max_tokens=20384,
            temperature=0.1
        )
        self.step_sender = kwargs.get("step_sender")
        print("Step sender class-",self.step_sender.agent_name)
        
    def _create_log_context(self):
        """Create a base logging context dictionary with common parameters."""
        context = {}
        if self.log_info:
            for key in ["user_id", "tenant_id", "session_id"]:
                if self.log_info.get(key):
                    context[key] = self.log_info.get(key)
        return context

    def _determine_primary_agent(self, user_context):
        try:
            agents = self._build_agent_descriptions()
            llm_prompt = primary_agent_prompt(conv=self.base_agent.conversation.format_conversation(
            ), user_context=user_context, agents=agents)
            primary_agent_response = self.base_agent.llm.run(
                llm_prompt, self.base_agent.modelOptions, 'agent::determine_primary_agent', self.log_info)
            print("debug -- _determine_primary_agent", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            primary_agent_name = result.get("primary_agent", '')
            self.primary_agent = self.agent_registry.get_agent(
                agent_name=primary_agent_name)(self.log_info)
            print("debug --", primary_agent_name, self.primary_agent)
        except Exception as e:
            print("error determine_primary_agent", e, traceback.format_exc())

    def _determine_blueprint(self, user_context):
        try:
            agents = self._build_agent_descriptions()
            llm_prompt = primary_agent_prompt(conv=self.base_agent.conversation.format_conversation(
            ), user_context=user_context, agents=agents)
            primary_agent_response = self.base_agent.llm.run(
                llm_prompt, self.base_agent.modelOptions, 'agent::determine_primary_agent', self.log_info)
            print("debug -- _determine_primary_agent", primary_agent_response)
            result = extract_json_after_llm(primary_agent_response)
            primary_agent_name = result.get("primary_agent", '')
            self.primary_agent = self.agent_registry.get_agent(
                agent_name=primary_agent_name)(self.log_info)
            print("debug --", primary_agent_name, self.primary_agent)
        except Exception as e:
            print("error determine_primary_agent", e, traceback.format_exc())

    def _build_agent_descriptions(self, detailed=False, agents=None) -> str:
        """
        Builds a description of all agents and optionally their functions.

        :param detailed: Whether to include function details in the descriptions.
        :return: A string containing descriptions of all agents and their functions (if detailed=True).
        """
        try:
            descriptions = []
            all_agents = agents
            if agents is None:
                all_agents = self.agent_registry.get_all_agents(
                    sessionID=self.log_info.get("session_id"))
            counter = 1
            # print(agents)
            # print(all_agents)
            for agent_name, agent_class in all_agents.items():
                descriptions.append(
                    f"{counter}. {agent_name} ___________________________")
                counter += 1
                agent_desc = f"Agent: {agent_name}\n{agent_class.description}"
                agent_desc = "\nHere are the functions that this agent can perform:\n"
                for func in agent_class.functions:
                    if detailed:
                        agent_desc += func.format_function()
                    else:
                        agent_desc += f"\n  - Function: {func.name}"
                descriptions.append(agent_desc)
            return "\n".join(descriptions)
        except Exception as e:
            print("error in _build_agent_descriptions ", e)
            return ""

    def _build_agent_descriptionsV2(self, detailed=False, agents=None) -> str:
        """
        Builds a description of all agents and optionally their functions.

        :param detailed: Whether to include function details in the descriptions.
        :reinforcement: the user responses on the features executed by these agents

        :return: A string containing descriptions of all agents and their functions (if detailed=True).
        """
        try:
            descriptions = []
            learnings = []

            # fetch all learnings and add in agent description
            # then the blueprint will have one step of reinforcement lookup for all the agents

            all_agents = agents
            if agents is None:
                all_agents = self.agent_registry.get_all_agents(
                    sessionID=self.log_info.get("session_id"))
            counter = 1
            # print(agents)
            # print(all_agents)
            for agent_name, agent_class in all_agents.items():
                descriptions.append(
                    f"{counter}. {agent_name} ___________________________")
                counter += 1
                agent_desc = f"Agent: {agent_name}\n{agent_class.description}"
                agent_desc = "\nHere are the functions that this agent can perform:\n"
                for func in agent_class.functions:
                    if detailed:
                        agent_desc += func.format_function()
                    else:
                        agent_desc += f"\n  - Function: {func.name}"
                descriptions.append(agent_desc)
            return "\n".join(descriptions)
        except Exception as e:
            print("error in _build_agent_descriptions ", e)
            return ""

    def _reinforcement_learning(self):
        try:
            pass
        except Exception as e:
            return

    def formatAvailableIntegrations(self, availableIntegrations):
        integrations = ""
        if not availableIntegrations:
            return "No Integrations"
        for integration in availableIntegrations:
            integrations += f"\n\n{integration.formatIntegration()}"
        return integrations
    
    def execute_function(self, agent_name, function):
        print("execute_function triggered")
        execute_func_timer = start_timer("execute_func_full", **self.log_context)

        conv = self.base_agent.conversation.format_conversation()
        last_tango_message = self.base_agent.conversation.last_tango_message()
        last_user_message = self.base_agent.conversation.last_user_message()
        
        system_prompt = f"""
        Your task is to look at the ongoing conversation and provide function arguments to the function that is being called.
        Here is the ongoing conversation: \n\n{conv} \n\n

        Return the arguments for the function in a json of the following format:
        ```json
        {{
            "arguments": {{
                "argument1": "value",
                "argument2": "value"
            }}
        }}
        ```
        """       
        user_message = f"""
        The function that is going to be called is described as: {function.format_function()}
        """
        chat = ChatCompletion(system_prompt, [], user_message)
        args = self.llm.run(chat, self.modelOptions , 'execute_function_args')
        args = extract_json_after_llm(args)['arguments']
        args = self._resolve_placeholders(args)

        try:
            agent_timer = start_timer("get_agent", 
                agent=agent_name, 
                **self.log_context)
            agent = self._get_agent(agent_name)(self.log_info)
            stop_timer(agent_timer)
            
            
            if not function:
                raise ValueError(f"Function '{function}' not found in primary agent '{agent.name}'.")

            args.update({
                'tenantID': self.log_info.get("tenant_id"),
                'userID': self.log_info.get("user_id"),
                'model_opts': self.base_agent.modelOptions,
                'eligibleProjects': self.base_agent.eligible_projects,
                'archivedProjects': self.base_agent.archived_projects,
                'llm': self.llm,
                "integrations": self.integrations,
                "sessionID": self.log_info.get("session_id"),
                "metadata": self.log_info.get("metadata"),
                "client_id": self.client_id,
                "last_tango_message": last_tango_message,
                "last_user_message": last_user_message,
                "socketio": self.socketio,
                "base_agent": self.base_agent
            })
        
            execute_function_timer = start_timer("execute_function", 
                                            agent=agent_name,
                                            function=function, 
                                            return_type=function.return_type,
                                            **self.log_context)
            
            output_str = ""
            for chunk in function.function(**args):
                output_str += chunk
                yield chunk
                
            stop_timer(execute_function_timer)
        
        except Exception as e:
            print("error here ", e, traceback.format_exc())

        stop_timer(execute_func_timer)
        self.tangoDataInserter.addTangoCode('')
        self.tangoDataInserter.addTangoData('')
        self.tangoDataInserter.addTangoResponse(output_str)
            
    def execute_alpha(self, user_context):
        print("in execute_alpha ", user_context)
        execute_alpha_timer = start_timer(
            "execute_alpha_full", **self.log_context)

        agents_timer = start_timer(
            "build_agents_description", **self.log_context)
        agents_detailed_description = self._build_agent_descriptions(
            detailed=True)
        stop_timer(agents_timer)

        integrations_timer = start_timer(
            "format_integrations", **self.log_context)
        integration_info = self.formatAvailableIntegrations(self.integrations)
        stop_timer(integrations_timer)

        blueprint_timer = start_timer("create_blueprint", **self.log_context)
        
        # print("--debug self.agent_registry.agents---",self.agent_registry.agents)
        agent = ",".join(self.agent_registry.agents.keys())
        print("---debug agent-----", agent)
        
        store_blueprint_code = True
        if agent in SKIP_BLUEPRINT_AGENTS and len(self.agent_registry.agents) == 1:
            agent_info = SKIP_BLUEPRINT_AGENTS[agent]
            store_blueprint_code = False
            # print("--debug skip_blueprint_agent: ",agent,"\nAgent Info: ",agent_info, "\nBlueprint store: ",store_blueprint_code)
            blueprint = {
                "thought_process": "",
                "feedback_required_from_user": agent_info["feedback_required_from_user"],
                "steps": [
                    {
                        "agent_name": agent,
                        "valid_arguments": agent_info["valid_arguments"],
                        "functions": [
                            {"name": func, "arguments": {}} for func in agent_info["functions"]
                        ]
                    }
                ]
            }
        
        else:
            blueprint = self.base_agent.create_blueprint_v3(
                agents_prompt=agents_detailed_description, user_context=user_context, integrations=integration_info, user_id=self.log_info.get("user_id"))
        stop_timer(blueprint_timer)

        conv = self.base_agent.conversation.format_conversation()
        last_tango_message = self.base_agent.conversation.last_tango_message()
        last_user_message = self.base_agent.conversation.last_user_message()
        prompt_combined = []
        output_combined = ''
        function_end_yield = ''
        functions_analysis_yield = ""
        should_execute_final = True

        functions_timer = start_timer("execute_blueprint_steps",
                                      step_count=len(
                                          blueprint.get("steps", [])),
                                      **self.log_context)
        for i, step in enumerate(blueprint.get("steps", [])):
            agent_name = step.get("agent_name")
            functions = step.get("functions", [])

            try:
                agent_timer = start_timer("get_agent",
                                          agent=agent_name,
                                          step=i,
                                          **self.log_context)
                agent = self._get_agent(agent_name)(self.log_info)
                stop_timer(agent_timer)

                functions_output = ''
                for j, function in enumerate(functions):
                    function_name = function.get("name")

                    print("looping -- ", function_name)
                    agent_function = next(
                        (func for func in agent.functions if func.name ==
                         function_name), None
                    )
                    if not agent_function:
                        raise ValueError(
                            f"Function '{function_name}' not found in primary agent '{agent.name}'.")

                    args = function.get("arguments")

                    resolve_args_timer = start_timer("resolve_args",
                                                     function=function_name,
                                                     **self.log_context)
                    args = self._resolve_placeholders(args)
                    stop_timer(resolve_args_timer)

                    function = agent_function.function

                    if function_name in ["create_portfolio"]:
                        db_timer = start_timer("insert_tango_state",
                                               key="STATE_LOCKED",
                                               **self.log_context)
                        TangoDao.insertTangoState(
                            tenant_id=self.log_info.get("tenant_id"),
                            user_id=self.log_info.get("user_id"),
                            key="STATE_LOCKED",
                            value=blueprint,
                            session_id=self.log_info.get("session_id")
                        )
                        stop_timer(db_timer)

                    args.update({
                        'tenantID': self.log_info.get("tenant_id"),
                        'userID': self.log_info.get("user_id"),
                        'model_opts': self.base_agent.modelOptions,
                        'model_opts2': self.modelOptions2,
                        'eligibleProjects': self.base_agent.eligible_projects,
                        'archivedProjects': self.base_agent.archived_projects,
                        'llm': self.llm,
                        "integrations": self.integrations,
                        "sessionID": self.log_info.get("session_id"),
                        "metadata": self.log_info.get("metadata"),
                        "client_id": self.client_id,
                        "last_tango_message": last_tango_message,
                        "last_user_message": last_user_message,
                        "socketio": self.socketio,
                        "base_agent": self.base_agent,
                        "step_sender": self.step_sender
                    })

                    execute_function_timer = start_timer("execute_function",
                                                         agent=agent_name,
                                                         function=function_name,
                                                         return_type=agent_function.return_type,
                                                         **self.log_context)
                    if agent_function.return_type == 'RETURN':
                        result = function(**args)
                    elif agent_function.return_type == "YIELD":
                        gen = function(**args)
                        chunk_size = 10
                        chunks = ""
                        try:
                            while True:
                                update = next(gen)
                                functions_analysis_yield += update
                                chunks += update

                                # Check if we've reached the desired chunk size
                                if len(chunks) >= chunk_size:
                                    yield chunks  # Yield the accumulated chunk
                                    chunks = ""  # Reset the chunk
                                # yield update
                        except StopIteration as e:
                            result = e.value
                    stop_timer(execute_function_timer)

                    if agent_function.type_of_func == AgentFnTypes.ACTION_TAKER_UI.name:
                        insert_timer = start_timer("insert_tango_data_action",
                                                   **self.log_context)
                        if store_blueprint_code:
                            self.tangoDataInserter.addTangoCode(blueprint)
                            self.tangoDataInserter.addTangoData('')
                        self.tangoDataInserter.addTangoResponse(result)
                        stop_timer(insert_timer)
                        yield result
                        should_execute_final = False
                        break

                    if agent_function.type_of_func == AgentFnTypes.SKIP_FINAL_ANSWER.name:
                        print("here .... store_blueprint_code-------", store_blueprint_code)
                        if store_blueprint_code:
                            self.tangoDataInserter.addTangoCode(blueprint)
                            self.tangoDataInserter.addTangoData('')
                        self.tangoDataInserter.addTangoResponse(
                            functions_analysis_yield)
                        # yield result
                        should_execute_final = False
                        # break

                    if isinstance(result, TangoYield):
                        for chunk in result.get_yield_now():
                            yield chunk
                        if result.get_yield_info() != "":
                            function_end_yield += (result.get_yield_info() + "\n")
                        result = result.get_return_info()

                    functions_output += f"""
                        -------------Execution of {i}th agent and {j}th function from the blueprint------
                        Agent Name - {agent_name.upper()}
                        Function Name - {function_name}
                        Data: Obtained: {str(result)}
                        -----------------------------
                    """
                output_combined += functions_output
                stop_timer(functions_timer)
            except Exception as e:
                print("error here ", e, traceback.format_exc())
            # I am thinking to
            # Stream individual responses if dynamic strategy
            # if response_strategy == "dynamic":
            #     for chunk in self.base_agent.stream_llm_response(result):
            #         yield chunk

        blueprint_string = json.dumps(blueprint)
        print("here .... 2")
        if should_execute_final:
            print("here .... 3")
            cta = True
            if list(self.agent_registry.get_all_agents().keys())[0] == "onboarding_agent":
                cta = False
            if list(self.agent_registry.get_all_agents().keys())[0] == "spend_agent":
                cta = False
            if list(self.agent_registry.get_all_agents().keys())[0] == "value_realization_agent":
                cta = False
            if "value_realization_agent" in blueprint_string:
                cta = False

            if blueprint.get("feedback_required_from_user") == "Text":
                cta = False

            agents_detailed_description = self._build_agent_descriptions()

            # print("debug if to use kbnowledge... ", '"capture_portfolio_knowledge": true' in blueprint_string)
            use_knowledge_layer = '"capture_portfolio_knowledge": true' in blueprint_string
            # use_knowledge_layer = True
            knowledgeData = None
            if use_knowledge_layer:
                knowledgeData = KnowledgeDao.FetchProjectPortfolioKnowledge(
                    tenant_id=self.log_info.get("tenant_id"), portfolio_id=None)
            prompt = response_prompt_of_combined_functions_v3(
                blueprint=blueprint,
                conv_history=conv,
                data=output_combined,
                cta=cta,
                agents_detailed_description=agents_detailed_description,
                knowledge_layer=knowledgeData
            )
            response_timer = start_timer(
                "generate_llm_response", **self.log_context)
            # print(prompt.formatAsString())
            string_response = functions_analysis_yield
            for chunk in self.base_agent.stream_llm_response(prompt):
                string_response += chunk
                yield chunk
            stop_timer(response_timer)

            string_response += function_end_yield
            yield function_end_yield

            self.tangoDataInserter.addTangoCode(blueprint)
            self.tangoDataInserter.addTangoData('')
            self.tangoDataInserter.addTangoResponse(string_response)

            stop_timer(execute_alpha_timer)

    # def execute_beta(self, user_context):
    #     ###################################### ... new logic ... #######################
    #     # If an agent was selected and it used an
    #     # action function like create portfolio
    #     # then we would have locked it in the conv
    #     # and now we should directly point to that locked agent and function..
    #     # and make the action function powerful enough to handle the conversation
    #     # and unlock the state if the action function thinks something is off
    #     locked_state = TangoDao.checkIfTangoLockedStateForConversation(user_id=self.log_info.get("user_id"), session_id=self.log_info.get("session_id"))
    #     print("checking locked in execute beta ", locked_state)
    #     if locked_state is None:
    #         for chunk in self.execute_alpha(user_context):
    #             yield chunk
    #     else:
    #         steps = locked_state["steps"]
    #         for i, step in steps:
    #             agent_name = step.get("agent_name")
    #             functions = step.get("functions", [])
    #             agent = self._get_agent(agent_name)(self.log_info)

    #             functions_output = ''
    #             for j, function in enumerate(functions):
    #                 function_name = function.get("name")
    #                 agent_function = next(
    #                     (func for func in agent.functions if func.name == function_name), None
    #                 )
    #                 if not agent_function:
    #                     raise ValueError(f"Function '{function_name}' not found in primary agent '{agent.name}'.")

    #                 args = function.get("arguments")
    #                 args = self._resolve_placeholders(args)
    #                 function = agent_function.function
    #                 args.update({
    #                     'tenantID': self.log_info.get("tenant_id"),
    #                     'userID': self.log_info.get("user_id"),
    #                     'model_opts': self.base_agent.modelOptions,
    #                     'eligibleProjects': self.base_agent.eligible_projects,
    #                     'llm': self.llm,
    #                     "integrations": self.integrations,
    #                     "sessionID": self.log_info.get("session_id"),
    #                     "metadata": self.log_info.get("metadata"),
    #                     "socketio": self.socketio,
    #                     "client_id": self.client_id,
    #                     "last_tango_message": last_tango_message,
    #                     "last_user_message": last_user_message,
    #                 })
    #                 result = function(**args)
    #                 ### lets think the rest later..

    def _resolve_placeholders(self, args: dict) -> dict:
        """
        Replaces placeholder values in args with corresponding values from the context.

        Args:
            args (dict): Arguments with potential placeholders.

        Returns:
            dict: Resolved arguments.
        """
        resolved_args = {}
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("<") and value.endswith(">"):
                placeholder = value.strip("<>")
                resolved_args[key] = self.context.get(placeholder)
            else:
                resolved_args[key] = value
        return resolved_args

    def _get_agent(self, agent_name: str):
        try:
            return self.agent_registry.get_agent(agent_name)
        except KeyError:
            raise ValueError(f"Agent '{agent_name}' is not registered.")

    def execute_plan(self, user_context):
        self._determine_primary_agent(user_context)
        agents = self._build_agent_descriptions(detailed=True)

        current_agent = self.primary_agent

        all_data_gathered = ''
        all_response_gathered = ''

        continued_conv = self.base_agent.conversation.format_conversation()

        max_loop = 3
        counter = 0
        thread_id = getShortUUID()
        thread_context = ''
        while True:

            counter += 1
            counter_id = f"{thread_id}_{counter}"
            if counter >= max_loop:
                print(
                    "No further steps suggested. Plan execution completed. max loop count")
                break
            # Generate the next step dynamically
            steps_executed_already = "\n".join(self.steps_executed)
            step = current_agent.create_next_step(
                steps_executed_already=steps_executed_already,
                agents_prompt=agents,
                conv=continued_conv,
            )

            if not step or not step.get("agent"):
                print("No further steps suggested. Plan execution completed.")
                break

            should_stop = step.get("should_stop", False)
            if should_stop:
                print(
                    "No further steps suggested. Plan execution completed. should stop true")
                break

            try:
                current_agent = self.agent_registry.get_agent(
                    agent_name=step.get("agent"))(self.log_info)
                agent_name = step["agent"]
                function_name = step["function"]
                args = step["args"]
                args = self._resolve_placeholders(args)
                agent = self._get_agent(agent_name)
                is_last = step["should_stop"] or counter == 2
                agent_function = next(
                    (func for func in agent.functions if func.name == function_name), None
                )
                if not agent_function:
                    raise ValueError(
                        f"Function '{function_name}' not found in agent '{agent_name}'.")

                function = agent_function.function
                args.update({
                    'tenantID': self.log_info.get("tenant_id"),
                    'userID': self.log_info.get("user_id"),
                    'eligibleProjects': self.base_agent.eligible_projects
                })
                output = function(**args)

                execution_info_string = f"""
                    \n
                    -----------execution start of agent function--------------------
                    <execution_id>
                    {counter_id}
                    <execution_id>
                    
                    The function: {agent_function.name} belonging to agent: {agent.name} 
                    is executed which was decided by the next step planner with the thought: {step["thought_process"]}.
                                        
                    Agent description: {agent.description} \
                    and it's function description: {agent_function.description} \
                    
                    
                    Got Output: 
                    <output_from_step_{counter_id}>
                        {output}
                    </output_from_step_{counter_id}>
                    -----------execution end of agent function--------------------
                    \n
                """
                thread_context += execution_info_string
                continued_conv += execution_info_string

                # print("debug conversation -- \n", execution_info_string, "\n")

                context_key = f"{agent_name}.{function_name}_output"
                prompt = response_prompt(
                    conv=thread_context, step_id=counter_id, is_first_step=counter == 1, is_last_step=is_last)
                string_data = ''

                for chunk in self.base_agent.stream_llm_response(prompt):
                    string_data += chunk
                    yield chunk

                print("debug response prompt -- \n",
                      prompt.formatAsString(), "\n")

                yield "\n\n"
                string_data += "\n\n"

                all_data_gathered += str(output)
                all_response_gathered += string_data

                response_string = f"""   
                    ------------                     
                    Response after running llm for data obtained by running agent in <execution_id>: {counter_id}.
                    <response_from_execution_id::{counter_id}>
                    {string_data}
                    <response_from_execution_id::{counter_id}>
                    ------------
                """
                continued_conv += response_string
                execution_info_string += response_string

                # print("debug conversation -- \n", response_string, "\n")
                self.context[context_key] = string_data
                self.steps_executed.append(str(step))
            except Exception as e:
                print(f"Error executing step: {step}",
                      e, traceback.format_exc())
                break

        self.tangoDataInserter.addTangoCode(self.steps_executed)
        self.tangoDataInserter.addTangoData(all_data_gathered)
        self.tangoDataInserter.addTangoResponse(all_response_gathered)

    def execute_new_workflow(self, user_context):
        """
        Executes a new workflow where a primary agent is identified,
        executes its own functions, and returns CTAs for the next steps.
        """
        thread_id = getShortUUID()

        accumulated_data = {}
        thread_context = ''
        execution_steps = []

        try:

            continued_conv = self.base_agent.conversation.format_conversation()
            planned_functions = self.create_blueprint(
                conv=continued_conv, user_context=user_context)
            full_plan = {
                "functions": planned_functions
            }
            print("debug ---planned_functions ", planned_functions)
            if not planned_functions:
                raise ValueError(
                    "Primary agent did not provide any planned functions.")

            for idx, function_plan in enumerate(planned_functions):
                function_name = function_plan["function"]
                args = function_plan["args"]
                args = self._resolve_placeholders(args)

                agent_function = next(
                    (func for func in current_agent.functions if func.name ==
                     function_name), None
                )
                if not agent_function:
                    raise ValueError(
                        f"Function '{function_name}' not found in primary agent '{current_agent.name}'.")

                function = agent_function.function
                args.update({
                    'tenantID': self.log_info.get("tenant_id"),
                    'userID': self.log_info.get("user_id"),
                    'eligibleProjects': self.base_agent.eligible_projects
                })
                output = function(**args)
                execution_id = f"{thread_id}_{idx + 1}"

                # Collect outputs
                accumulated_data[execution_id] = output
                step_info = f"""
                    -----------execution start of agent function--------------------
                    Execution ID: {execution_id}
                    Agent: {current_agent.name}
                    Function: {function_name}
                    Output: {output}
                    -----------execution end of agent function--------------------
                """
                thread_context += step_info

            info = f"""
                So, The primary agent: {current_agent.name} with the description: {current_agent.description}
                created a plan to execute multiple functions to accumulate data:
                All functions executed and data:
                {thread_context}
                
                This is done to help create the best possible response to help the user with this need.
            """
            continued_conv += info
            agents_prompt = self._build_agent_descriptions()

            prompt = response_prompt_for_workflow3(
                conv=continued_conv, agents_prompt=agents_prompt)
            print("debug-response_prompt_for_workflow3", prompt.formatAsString())
            string_response = ''
            for chunk in self.base_agent.stream_llm_response(prompt):
                string_response += chunk
                yield chunk

            self.tangoDataInserter.addTangoCode(full_plan)
            self.tangoDataInserter.addTangoData(info)
            self.tangoDataInserter.addTangoResponse(string_response)

        except Exception as e:
            print(f"Error during primary agent function execution: {e}")
            traceback.print_exc()
            return {"error": str(e)}

    def create_blueprint(self, conv, user_context):
        print("create_blueprint ")
        agents = self.mini_blueprint(conv, user_context)
        agents_dict = {}
        for agent in agents:
            agent_instance = self.agent_registry.get_agent(agent_name=agent)
            agents_dict[agent] = agent_instance
            print(agents_dict)
        agent_desc = self._build_agent_descriptions(
            detailed=True, agents=agents_dict)
        print(agent_desc)
        prompt = f"""
        You are responsible for creating a blueprint for actions to be taken in response to a user query. The layout will be as follows:
        Agents will be selected to make actions based on the user's query and context. Each Agent has certain functions that can be called.
        
        Here are the agents that you can choose from and their respective functions:
        {agent_desc}
        
        The user has asked asked you a question. First, the user's context is such: {user_context}.
        
        The user has asked for help with the following: {conv}
        
        Please create a blueprint for which agents to use and which functions to call in order.
        
        Output Format (JSON):
        ```json
        [
            {{
                "agent": "<agent_name>",
                "function": "<name_of_function>",
                "args": {{
                    "<arg1>": "<value1>",
                    "<arg2>": "<value2>"
                }},
                "short_reason": "<short_reason_for_choosing_this_function>"
            }},...
        ]
        ```
        
        You can leave the value of each argument as "<value>" if you are unsure of the value to provide. This is reasonable as the agents you selected may need to be called for the correct fields to be determined.\
        """

        prompt = ChatCompletion(
            system=AI_INTRO,
            prev=[],
            user=prompt
        )

        response = self.llm.run(prompt, self.modelOptions,
                                "create_blueprint", self.log_info)
        print("create_blueprint ", prompt.formatAsString())
        print("create_blueprint response", response)
        response_json = extract_json_after_llm(response)

    def mini_blueprint(self, conv, user_context):
        agents = self._build_agent_descriptions(detailed=False)
        print(agents)
        prompt = f"""
        You are responsible for deciding which of provided agents could be useful in fulfilling the user's request.
        
        First, the user's context is such: {user_context}.
        
        The user has asked for help with the following: {conv}
        
        Here are the agents that you can choose from:
        {agents}
        
        Obviously, if only one agent is provided to you, you must choose that agent.
        
        Please respond with a json object of containing a list of the agents you would like to use.
        
        For example:
        
        ```json
        {{
            agent: ["<name_of_agent_1>, <name_of_agent_2>, ..."],
        }}
        """

        prompt = ChatCompletion(
            system=AI_INTRO,
            prev=[],
            user=prompt
        )

        response = self.llm.run(prompt, self.modelOptions,
                                "agent::mini_blueprint", self.log_info)
        print("mini_blueprint ", prompt.formatAsString())
        print("mini_blueprint response", response)
        response_json = extract_json_after_llm(response)
        agents = response_json.get("agent", [])
        return agents

    def plan_functions(self, conv, user_context):
        agent_name = self.primary_agent.name
        agent_description = self.primary_agent.description

        all_functions = self._build_function_descriptions(detailed=True)
        data_for_blueprint = self.primary_agent.fetch_data_for_blueprint_creation()

        return self.primary_agent.plan_functions(data=data_for_blueprint, agents_prompt=all_agents_and_functions, conv=conv, user_context=user_context, agent_name=agent_name)

    def execute_plan_v2(self, user_context):
        agents_prompt = self._build_agent_descriptions(detailed=True)
        current_agent = self.base_agent

        continued_conv = self.base_agent.conversation.format_conversation()
        blueprint = current_agent.create_blueprint(
            agents_prompt, continued_conv)

        all_data_gathered = ''
        all_response_gathered = ''

        for step in blueprint.get('chain_of_agents', []):
            agent_name = step['agent']
            agent_instance = self.agent_registry.get_agent(
                agent_name=agent_name)(self.log_info)
            if not agent_instance:
                continue

            function_name = step["function"]
            args = step["args"]
            args = self._resolve_placeholders(args)
            agent_function = next(
                (func for func in agent_instance.functions if func.name ==
                 function_name), None
            )
            if not agent_function:
                raise ValueError(
                    f"Function '{function_name}' not found in agent '{agent_name}'.")

            function = agent_function.function
            args.update({
                'tenantID': self.log_info.get("tenant_id"),
                'userID': self.log_info.get("user_id"),
                'eligibleProjects': self.base_agent.eligible_projects
            })
            output = function(**args)
            all_data_gathered += "\n\n" + \
                f"Data Obtained after executing {function_name}" + str(output)

        #######
        prompt = response_prompt_of_combined_functions_v2(
            conv=self.base_agent.conversation.format_conversation(),
            blueprint=blueprint,
            data=all_data_gathered
        )
        print("*****", prompt.formatAsString())
        for chunk in self.base_agent.stream_llm_response(prompt):
            all_response_gathered += chunk
            yield chunk
        #######

        self.tangoDataInserter.addTangoCode(self.steps_executed)
        self.tangoDataInserter.addTangoData(all_data_gathered)
        self.tangoDataInserter.addTangoResponse(all_response_gathered)



    
SKIP_BLUEPRINT_AGENTS = {
    
    "customer_success_agent": {"functions": ["manage_bug_enhancement"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "integration_agent": {"functions": ["integration_agent_fn"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "analyst": {"functions": ["view_combined_analysis"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "knowledge_agent": {"functions": ["view_knowledge_graph_analysis"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "project_creation_agent": {"functions": ["project_creation_agent"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "roadmap_agent": {"functions": ["roadmap_agent"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "quantum_agent": {"functions": ["quantum_onboard"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "potential_agent": {"functions": ["potential_analyst"],"valid_arguments": "","feedback_required_from_user": "Text"},
    "idea_ranking_agent": {"functions": ["idea_ranking_agent"],"valid_arguments": "","feedback_required_from_user": "Text"}
}