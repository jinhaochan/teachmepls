import asyncio
from flask import Flask, render_template, request, redirect, url_for, session
from tutor import TutorAgenticSystem

from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change for production

def get_tutor():
    topic = session.get("topic")
    level_index = session.get("level_index", 0)
    topic_history = session.get("topic_history", [])
    evaluations = session.get("evaluations", [])
    suggestions = session.get("suggestions", [])
    return TutorAgenticSystem(topic, level_index, topic_history, evaluations, suggestions)

def save_tutor(tutor):
    session["topic"] = tutor.topic
    session["level_index"] = tutor.level_index
    session["topic_history"] = tutor.topic_history
    session["evaluations"] = tutor.evaluations
    session["suggestions"] = tutor.suggestions

def require_topic(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "topic" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        topic = request.form["topic"]
        session.clear()
        session["topic"] = topic
        session["level_index"] = 0
        session["topic_history"] = []
        session["evaluations"] = []
        session["suggestions"] = []
        return redirect(url_for("quiz"))
    return render_template("index.html")

@app.route("/quiz", methods=["GET", "POST"])
@require_topic
def quiz():
    tutor = get_tutor()
    if request.method == "POST":
        questions = session.get("questions", [])
        # Use a global index for field names to match the template
        answers = []
        for idx, q in enumerate(questions):
            subtopic = q['subtopic']
            question = q["question"]
            field_name = f"answer_{subtopic}_{idx+1}"
            print(field_name)
            answer = request.form.get(field_name, "")
            answers.append((subtopic, question, answer))
        results = {}
        print(answers)
        for subtopic, question, answer in answers:
            eval_result = asyncio.run(tutor.evaluate_answer(question, answer))
            feedback = eval_result["feedback"]
            score = eval_result["score"]
            if subtopic not in results:
                results[subtopic] = []
            results[subtopic].append({
                "question": question,
                "answer": answer,
                "feedback": feedback,
                "score": score
            })
        session["results"] = results
        return redirect(url_for("gate"))
    subtopics = asyncio.run(tutor.generate_subtopics())
    questions = asyncio.run(tutor.generate_quiz(subtopics))
    session["subtopics"] = subtopics
    session["questions"] = questions

    save_tutor(tutor)
    return render_template("quiz.html", questions=questions, level=tutor.level)

@app.route("/gate", methods=["GET", "POST"])
@require_topic
def gate():
    tutor = get_tutor()
    subtopics = session.get("subtopics", [])
    results = session.get("results", {})

    # Calculate scores and feedbacks from results
    scores = []
    feedbacks = []
    questions = []
    for subtopic, items in results.items():
        for item in items:
            scores.append(item["score"])
            feedbacks.append(item["feedback"])
            questions.append({"subtopic": subtopic, "question": item["question"], "answer": item["answer"]})

    # Calculate average score per subtopic
    subtopic_scores = {}
    for subtopic, items in results.items():
        subtopic_scores[subtopic] = [item["score"] for item in items]
    subtopic_avg_scores = {k: (sum(v) / len(v) if v else 0.0) for k, v in subtopic_scores.items()}

    avg_score = sum(scores) / len(scores) if scores else 0.0

    result = asyncio.run(tutor.gate_decision(subtopics, subtopic_avg_scores))
    save_tutor(tutor)
    advance = result.get("advance", False)
    reason = result.get("reason", "")
    additional_subtopics = result.get("additional_subtopics", [])
    completed = tutor.level == "advanced" and advance

    if request.method == "POST":
        if avg_score <= 0.7:
            return redirect(url_for("quiz"))
        if additional_subtopics:
            tutor.topic_history += subtopics
            save_tutor(tutor)
            questions = asyncio.run(tutor.generate_quiz(additional_subtopics))
            session["questions"] = questions
            save_tutor(tutor)
            return redirect(url_for("quiz"))
        elif completed:
            session.clear()
            return render_template("complete.html")
        elif advance:
            tutor.topic_history += subtopics
            save_tutor(tutor)
            tutor.advance()
            save_tutor(tutor)
            return redirect(url_for("quiz"))
        else:
            return redirect(url_for("quiz"))
    return render_template(
        "gate.html",
        advance=advance,
        reason=reason,
        additional_subtopics=additional_subtopics,
        level=tutor.level,
        feedbacks=feedbacks,
        scores=scores,
        avg_score=avg_score,
        subtopic_avg_scores=subtopic_avg_scores,
        completed=completed,
        results=results,
    )

if __name__ == "__main__":
    app.run(debug=True)

