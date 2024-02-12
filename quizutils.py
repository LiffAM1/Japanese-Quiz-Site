import os
from models import *

class QuizUtils:
    @staticmethod
    def score(user: User, quiz: Quiz, data: dict):
        results = QuizAttempt(user.id, quiz.id, quiz.title, data['question_language'], data['answer_language'], 0, {})
        response_data = data['responses']
        user_answers = {}
        total_correct = 0
        for (id, question) in quiz.questions.items():
            response = response_data[str(id)]
            answers = question.get_answers(data['answer_language'])
            formatted_response = QuizUtils.format_question_answer(response['answer'])
            formatted_answers = [QuizUtils.format_question_answer(a) for a in answers]
            correct = (formatted_response in formatted_answers) or (formatted_response == ("or").join(formatted_answers))
            user_answers[id] = QuizResponse(id, question.get_question(data['question_language']), answers, response['answer'], correct)
            total_correct = total_correct + 1 if correct else total_correct
        results.score = total_correct/len(quiz.questions)
        results.responses = user_answers
        return results

    @staticmethod
    def format_question_answer(string):
        string = string.lower()

        # Ignores all spaces, punctuation, etc so we don't grade on dumb differences
        strings_to_replace = ["'", ",", ".", "!", "?", " ", '"','\\"', "_", "。", "(beginning)", "(end)"]
        for s in strings_to_replace:
            string = string.replace(s,"")
        return string.strip()

    @staticmethod
    def calculate_leaderboard(formatted_users):
        formatted_users.sort(key=lambda u: u['average_score_float']*u['count_quizzes'], reverse=True)
        leaderboard_results = \
            {u['id']: LeaderboardRank(i, u['id'], u['display_name'], u['count_quizzes'], u['average_score']) for i, u in enumerate(formatted_users, 1)}
        return leaderboard_results
