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
        self.question_history = []
        self.evaluations = []
        self.suggestions = []
        self.quiz_agent = self._create_quiz_agent()
        self.evaluation_agent = self._create_evaluation_agent()
        self.gate_agent = self._create_gate_agent()

    def _create_quiz_agent(self) -> Agent:
        previous_questions = '\n'.join(self.question_history)
        suggested_topics = '\n'.join(self.suggestions)
        return Agent(
            name="quiz-generator",
            instructions=f"""
            You are a quiz generator. 
            The topic is "{self.topic}".
            Generate {self.number_of_questions} different short-answer questions about {self.topic} at a {self.level} level
            These questions were covered before previously: 
            {previous_questions}
            These topics are suggested to be covered: 
            {suggested_topics}
            Do not provide answers.
            Respond in JSON only without markdown so i can immediately parse the output:
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
            Respond in JSON only without markdown so i can immediately parse the output:
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
            - Must not advance if there are suggested topics to cover
            - Must have average score >= 0.7
            - ONLY advance when the user scores >= 0.7, and there are no suggested topics left to cover
            Respond in JSON only without markdown so i can immediately parse the output:
            {{
                "advance": boolean,
                "reason": "string",
                "suggestions": ["list of strings"]
            }}
            """,
        )

    async def generate_quiz(self):
        response = await Runner.run(self.quiz_agent, f"topic: {self.topic}\n\nlevel: {self.level}")
        generated_questions = json.loads(response.final_output)
        question_list = []

        for q_number in generated_questions:
            question = generated_questions[q_number]
            question_list.append(question)

        # updating memory of questions asked
        self.question_history += question_list

        return question_list

    async def evaluate_answer(self, question: str, answer: str):
        result = await Runner.run(self.evaluation_agent, f"question: {question},\n\n\nanswer: {answer}")
        eval_data = json.loads(result.final_output)
        self.evaluations.append(result.final_output)

        return eval_data

    async def gate_decision(self):
        evals = str(self.evaluations)
        result = await Runner.run(self.gate_agent, f"evaluations:\n\n {evals}")
        result_data = json.loads(result.final_output)

        self.suggestions = result_data['suggestions']
        return result_data


    def advance(self):
        self.level_index += 1
        self.level = self.LEVELS[self.level_index]


# === Example Usage ===
if __name__ == "__main__":
    topic = input("Enter the topic you want to learn about: ")

    tutor = TutorAgenticSystem(topic)

    while True:
        print(f"\n=== Level: {tutor.level.capitalize()} ===")

        # Step 1: Generate Questions
        questions = asyncio.run(tutor.generate_quiz())

        for question in questions:
            print(question)
            answer = input()

            eval_result = asyncio.run(tutor.evaluate_answer(question, answer))
            print(f"Score: {eval_result['score']}")
            print(f"Feedback: {eval_result['feedback']}\n")

        # Step 3: Gatekeeping
        result = asyncio.run(tutor.gate_decision())
        print("\n--- Gate Result ---")

        advance = result['advance']
        reason = result['reason']
        suggestions = result['suggestions']

        print(f"Advance to next level: {advance}")
        print(f"Reason: {reason}")
        print(f"Suggestions for {tutor.level} level:")

        if len(suggestions) == 0:
            print("None")
        else:
            for suggestion in suggestions:
                print(suggestion)

        if advance == True:
            print("advancing")
            tutor.advance()

        if tutor.level == "advanced":
            print("\n🎉 You completed all levels! Well done.")
            break

