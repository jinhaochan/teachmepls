import asyncio
import json

from agents import Agent, Runner


class TutorAgenticSystem:
    LEVELS = ["beginner", "intermediate", "advanced"]

    def __init__(self, topic: str):
        self.topic = topic
        self.level_index = 0 # always start at level 0
        self.level = self.LEVELS[self.level_index]
        self.number_of_questions = 5
        self.quiz_agent = self._create_quiz_agent()
        self.evaluation_agent = self._create_evaluation_agent()
        self.gate_agent = self._create_gate_agent()
        self.questions = []
        self.evaluations = []

    def _create_quiz_agent(self) -> Agent:
        return Agent(
            name="quiz-generator",
            instructions=f"""
            You are a quiz generator. 
            The topic is "{self.topic}".
            Generate {self.number_of_questions} different short-answer questions about {self.topic} at a {self.level} level
            Do not provide answers.
            Respond in JSON only:
            {{
                "q1" : "...",
                "q2" : "...",
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
            Respond in JSON only:
            {{
                "score": float (0-1),
                "feedback": "string",
            }}
            """,
        )

    def _create_gate_agent(self) -> Agent:
        return Agent(
            name="gate-agent",
            instructions=f"""
            You are a an expert on the topic of "{self.topic}".
            Given the list of evaluations for all quiz questions,
            decide if the user can advance to the next level.
            Rules:
            - Must not advance if key concepts are missing in the questions at a {self.level} level
            - Must have average score >= 0.7
            Respond in JSON only:
            {{
                "advance": true/false,
                "reason": "string",
                "suggested_focus": ["list of strings"]
            }}
            """,
        )

    async def generate_quiz(self):
        response = await Runner.run(self.quiz_agent, f"topic: {self.topic}\n\nlevel: {self.level}")
        self.questions = response.final_output
        return self.questions

    async def evaluate_answer(self, question: str, answer: str):
        result = await Runner.run(self.evaluation_agent, f"question: {question},\n\n\nanswer: {answer}")
        self.evaluations.append(result.final_output)
        return result.final_output

    async def gate_decision(self):
        evals = str(self.evaluations)
        result = await Runner.run(self.gate_agent, f"evaluations:\n\n {evals}")
        return result.final_output


# === Example Usage ===
if __name__ == "__main__":
    topic = input("Enter the topic you want to learn about: ")

    tutor = TutorAgenticSystem(topic)

    while True:
        print(f"\n=== Level: {tutor.level.capitalize()} ===")

        # Step 1: Generate Questions
        questions = asyncio.run(tutor.generate_quiz())
        q_data = json.loads(questions)

        for q_number in q_data:
            question = q_data[q_number]
            print(f"{q_number}: {question}")
            answer = input()

            eval_result = asyncio.run(tutor.evaluate_answer(question, answer))
            eval_data = json.loads(eval_result)
            print(f"Score: {eval_data['score']}")
            print(f"Feedback: {eval_data['feedback']}\n")

        # Step 3: Gatekeeping
        result = asyncio.run(tutor.gate_decision())
        print("\n--- Gate Result ---")
        print(result)

        if not result.get("advance", False):
            print(f"\nYou did not advance. Stay at level: {tutor.level.capitalize()}")
            break

        if tutor.level == "advanced":
            print("\n🎉 You completed all levels! Well done.")
            break

