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
            correct = QuizUtils.format_question_answer(response['answer']) in [QuizUtils.format_question_answer(a) for a in answers]
            user_answers[id] = QuizResponse(id, question.get_question(data['question_language']), answers, response['answer'], correct)
            total_correct = total_correct + 1 if correct else total_correct
        results.score = total_correct/len(quiz.questions)
        results.responses = user_answers
        return results

    @staticmethod
    def format_question_answer(string):
        string = string.lower()

        strings_to_replace = ["_", "(beginning)", "(end)"]
        for s in strings_to_replace:
            string = string.replace(s,"")
        return string.strip()

    @staticmethod
    def calculate_average_score(user, results):
        total_count = user.count_quizzes + 1
        return ((user.average_score * user.count_quizzes) + results.score)/total_count

    @staticmethod
    def calculate_leaderboard(users):
        place = 0
        users.sort(key=lambda u: u.average_score*u.count_quizzes, reverse=True)
        leaderboard_results = \
            {u.id: LeaderboardRank(i, u.id, u.display_name, u.count_quizzes, u.average_score) for i, u in enumerate(users, 1)}
        return leaderboard_results

    @staticmethod
    def format_percent(n):
        return "{:.2f}%".format(n*100)
