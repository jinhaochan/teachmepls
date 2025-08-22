import json
from agents import Agent, Runner

class TutorAgenticSystem:
    LEVELS = ["beginner", "intermediate", "advanced"]

    def __init__(self, topic: str, level_index=0, topic_history=None, evaluations=None, suggestions=None):
        self.topic = topic
        self.level_index = level_index
        self.level = self.LEVELS[self.level_index]
        self.number_of_questions = 1
        self.topic_count = 3
        self.topic_history = topic_history or []
        self.evaluations = evaluations or []
        self.suggestions = suggestions or []
        self.quiz_agent = self._create_quiz_agent()
        self.evaluation_agent = self._create_evaluation_agent()
        self.gate_agent = self._create_gate_agent()

    def _create_quiz_agent(self, topics=None) -> Agent:
        topics = topics or [self.topic]
        suggested_topics = '\n'.join(self.suggestions)
        topics_str = ', '.join(topics)
        return Agent(
            name="quiz-generator",
            instructions=f"""
            You are a quiz generator.
            The main topic is "{self.topic}".
            Subtopics to cover: {topics_str}
            For each subtopic, generate {self.number_of_questions} different short-answer questions about that subtopic at a {self.level} level.
            These topics are suggested to be covered:
            {suggested_topics}
            Do not provide answers.
            Respond in JSON only without markdown so I can immediately parse the output:
            {{
                "subtopic1": {{
                    "q1": "...",
                    "q2": "...",
                    ...
                }},
                "subtopic2": {{
                    "q1": "...",
                    "q2": "...",
                    ...
                }},
                ...
            }}
            """,
        )

    def _create_evaluation_agent(self) -> Agent:
        return Agent(
            name="evaluation-agent",
            instructions=f"""
            You are an expert on the topic of {self.topic}.
            You are to act as an evaluator to the candidates answers.
            Given a question and a user's answer, evaluate correctness
            in the context of {self.topic}.
            Respond in JSON only without markdown so i can immediately parse the output:
            {{
                "score": float (0-1),
                "feedback": "string",
            }}
            """,
        )

    def _create_gate_agent(self, subtopics=None, subtopic_avg_scores=None) -> Agent:
        subtopics = subtopics or []
        subtopic_avg_scores = subtopic_avg_scores or {}
        subtopics_str = ', '.join(subtopics)
        subtopic_scores_json = json.dumps(subtopic_avg_scores)
        return Agent(
            name="gate-agent",
            instructions=f"""
            You are an expert on the topic of "{self.topic}".
            Subtopics: [{subtopics_str}]
            Subtopic average scores: {subtopic_scores_json}
            Decide if the user can advance to the next level.
            Rules:
            - Must not advance if there are subtopics with average score < 0.7
            - Must have overall average score >= 0.7
            - ONLY advance when the user scores >= 0.7 on all subtopics, and there are no additional subtopics left to cover
            Additionally, evaluate if the current subtopics are sufficient for mastering "{self.topic}" at a {self.level} level.
            If the subtopics are insufficient, generate an additional list of subtopics that should be covered.
            If any subtopic's average score < 0.7, add it to additional_subtopics list.
            Respond in JSON only without markdown so I can immediately parse the output:
            {{
                "advance": boolean,
                "reason": "string",
                "additional_subtopics": ["list of new subtopics to test"]            }}
            """,
        )

    def _create_subtopic_agent(self) -> Agent:
        return Agent(
            name="subtopic-generator",
            instructions=f"""
            You are a subtopic generator.
            Given the topic "{self.topic}", generate a list of {self.topic_count} MOST relevant subtopics 
            The chosen topics should allow the user to master this topic at a {self.level} level.
            Respond in JSON only without markdown so I can immediately parse the output:
            {{
                "subtopics": ["subtopic 1", "subtopic 2" ...]
            }}
            """,
        )

    async def generate_quiz(self, topics=None):
        agent = self._create_quiz_agent(topics)
        response = await Runner.run(agent, f"topic: {self.topic}\n\nlevel: {self.level}\nsubtopics: {topics or [self.topic]}")
        generated_questions = json.loads(response.final_output)
        question_list = []
        for subtopic, questions in generated_questions.items():
            for _, question in questions.items():
                question_list.append({"subtopic": subtopic, "question": question})
        return question_list

    async def evaluate_answer(self, question: str, answer: str):
        result = await Runner.run(self.evaluation_agent, f"question: {question},\n\n\nanswer: {answer}")
        eval_data = json.loads(result.final_output)
        self.evaluations.append(result.final_output)
        return eval_data

    async def gate_decision(self, subtopics=None, subtopic_avg_scores=None):
        subtopics = subtopics or []
        subtopic_avg_scores = subtopic_avg_scores or {}
        gate_agent = self._create_gate_agent(subtopics, subtopic_avg_scores)
        subtopic_scores_json = json.dumps(subtopic_avg_scores)
        result = await Runner.run(
            gate_agent,
            f"subtopics: {subtopics}\nsubtopic_avg_scores: {subtopic_scores_json}"
        )
        result_data = json.loads(result.final_output)
        self.additional_subtopics = result_data.get('additional_subtopics', [])
        return result_data

    async def generate_subtopics(self):
        subtopic_agent = self._create_subtopic_agent()
        response = await Runner.run(subtopic_agent, f"topic: {self.topic}")
        subtopics = json.loads(response.final_output)["subtopics"]
        return subtopics

    def advance(self):
        self.level_index += 1
        self.level = self.LEVELS[self.level_index]
        self.quiz_agent = self._create_quiz_agent()
        self.evaluation_agent = self._create_evaluation_agent()
        self.gate_agent = self._create_gate_agent()