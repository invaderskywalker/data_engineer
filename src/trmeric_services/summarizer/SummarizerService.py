from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_services.summarizer.Prompt import *
from src.trmeric_api.logging.AppLogger import appLogger


class SummarizerService:

    def __init__(self, logInfo, word_count_threshold=30000):
        self.llm = ChatGPTClient()
        self.modelOptions = ModelOptions(
            model="gpt-4o-mini",
            max_tokens=4384,
            temperature=0.3
        )
        self.logInfo = logInfo
        self.word_count_threshold = word_count_threshold

    def word_count(self, text):
        try:
            return len(text.split())
        except Exception as e:
            return 0

    def chunk_data(self, data, chunk_size):
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def summarizer(self, large_data, message, identifier="jira", fn=''):
        appLogger.info({
            "event": "debug_summarizer",
            "logInfo": self.logInfo,
            "function": fn,
            "word_count": self.word_count(large_data)
        })
        if self.word_count(large_data) < self.word_count_threshold:
            print(f"Data is below word count threshold. Returning original data.")
            appLogger.info({"event": "summarizer", "word_count": self.word_count(
                large_data), "message": "Data is below word count threshold"})
            return large_data  # Directly return data if it's below the threshold

        if identifier == "jira":
            return self.jira_summarizer(large_data, message)
        if identifier == "ado":
            return self.ado_summarizer(large_data, message)
        if identifier == "files_uploaded":
            return self.files_uploaded_summarizer(large_data, message)
        if identifier == "chat":
            return self.chat_summarizer(large_data, message)
        if identifier == 'smartsheet':
            return self.smartsheet_summarizer(large_data, message)
        if identifier == 'github':
            return self.github_summarizer(large_data, message)
        if identifier == 'confluence':
            return self.confluence_summarizer(large_data, message)

    def chat_summarizer(self, large_data, message):
        chunk_size = 100000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            print("--debug running chat summary")
            appLogger.info({"event": "summarizer", "count": len(summaries)})
            prompt = createChatSummary(chunk, message)
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "chat_summarizer",
                logInDb=self.logInfo,
            )
            summaries.append(response)
        return "\n\n\n".join(summaries)

    def files_uploaded_summarizer(self, large_data, message):
        chunk_size = 40000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            print("--debug running fileUpload summary")
            prompt = createDocSummary(chunk, message)
            response = self.llm.run(
                prompt,
                self.modelOptions,
                "process_uploaded_files",
                logInDb=self.logInfo,
            )
            summaries.append(response)

        return " <separator> ".join(summaries)

    def ado_summarizer(self, large_data, message):
        chunk_size = 40000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            print("running summary ado-------")

            prompt = createAdoSummary(chunk, message)
            result = self.llm.run(
                prompt,
                self.modelOptions,
                "ado_summarizer",
                logInDb=self.logInfo
            )
            summaries.append(result)

        return " <separator> ".join(summaries)

    def jira_summarizer(self, large_data, message):
        chunk_size = 100000
        summaries = []
        print('debug ', len(large_data))

        for chunk in self.chunk_data(large_data, chunk_size):
            print("running summary jira-------", len(chunk))

            prompt = createJiraSummary(chunk, message)
            result = self.llm.run(
                prompt,
                self.modelOptions,
                "jira_summarizer",
                logInDb=self.logInfo
            )
            summaries.append(result)

        return " <separator> ".join(summaries)

    def confluence_summarizer(self, large_data, message):
        chunk_size = 100000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            # print("running summary confluence-------")

            prompt = createConfluenceSummary(chunk, message)
            result = self.llm.run(
                prompt,
                self.modelOptions,
                "jira_summarizer",
                logInDb=self.logInfo
            )
            summaries.append(result)

        return "".join(summaries)

    def smartsheet_summarizer(self, large_data, message):
        chunk_size = 40000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            print("running smartsheet_summarizer-------")

            prompt = createSmartSheetSummary(chunk, message)
            result = self.llm.run(
                prompt,
                self.modelOptions,
                "smartsheet_sumarizer",
                logInDb=self.logInfo
            )
            summaries.append(result)

        return " <separator> ".join(summaries)

    def github_summarizer(self, large_data, message):
        chunk_size = 200000
        summaries = []

        for chunk in self.chunk_data(large_data, chunk_size):
            print("running github_summarizer-------")

            prompt = createGithubSummary(chunk, message)
            result = self.llm.run(
                prompt,
                self.modelOptions,
                "github_sumarizer",
                logInDb=self.logInfo
            )
            summaries.append(result)

        return " <separator> ".join(summaries)

    def ongoing_summarizer(self, large_data, message):
        chunk_size = 150000
        summaries = []
        summary = ''
        print('debug ', len(large_data))

        for chunk in self.chunk_data(large_data, chunk_size):
            print("running ongoing_summarizer-------", len(chunk))

            prompt = ongoingSummarizerJiraMetricsV2(summary, chunk, message)
            summary = self.llm.run(
                prompt,
                self.modelOptions,
                "ongoing_summarizer",
                logInDb=self.logInfo
            )
            # prompt = createJiraSummary(chunk, message)
            # result = self.llm.run(
            #     prompt,
            #     self.modelOptions,
            #     "ongoing_summarizer",
            #     logInDb=self.logInfo
            # )
            # summaries.append(result)
            # print("intermediate summary --- ", summary)
        return summary
        # summaries.append(result)

        # return "  ".join(summaries)
