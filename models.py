import os
import random
from datetime import datetime 
from miscutils import MiscUtils

BASE_URL = os.environ.get("BASE_URL", None)

class User:
    def __init__(self, id: str, name: str, display_name: str, email: str, average_score: float, count_quizzes: int, is_active: bool, is_authenticated: bool):
        self.id = id
        self.name = name
        self.email = email
        self.display_name = display_name
        self.average_score = average_score
        self.count_quizzes = count_quizzes
        self.is_active = is_active
        self.is_authenticated = is_authenticated

    def get_id(self):
        return self.id
    
    @staticmethod
    def from_dict(dict: dict):
        return User(dict['id'], dict['name'], dict['display_name'], dict['email'], dict['average_score'], \
            dict['count_quizzes'], dict['is_active'], dict['is_authenticated'])

    def to_dict(self):
        return self.__dict__

    def to_display_dict(self):
        user = self.to_dict()
        user['average_score'] = MiscUtils.format_percent(self.average_score)
        return user

class Quiz:
    def __init__(self, id: str, title: str, level: str, questions: dict):
        self.id = id
        self.title = title
        self.link = self.get_link()
        self.level = level 
        self.questions = questions # dict[question id, QuizQuestion]
        self.questions_list = questions.values() # making life easier with Jinja
    
    def get_link(self):
        return f"{BASE_URL}/quiz/{self.id}"

    @staticmethod
    def from_dict(dict: dict):
        return Quiz(dict['id'], dict['title'], dict['level'], \
            {qq.id: qq for qq in [QuizQuestion.from_dict(q) for q in dict['questions']]})

    def get_quiz_view(self, question_language: str):
        view = {
            'id': self.id,
            'title': self.title,
            'link': self.link,
            'level': self.level,
            'questions': [{
                'id': q.id,
                'question': q.get_question(question_language)
            } for q in self.questions.values()]
        }

        # Don't return the questions in the same order each time
        random.shuffle(view['questions'])
        return view


    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'link': self.link,
            'level': self.level,
            'questions': {k: q.__dict__ for k,q in self.questions.items()},
            'questions_list': [q.__dict__ for q in self.questions_list]
        }
    
class QuizQuestion:
    def __init__(self, id: str, english: list, romanji: list, hiragana: list):
        self.id = id
        self.english = english # list[string]
        self.romanji = romanji # list[string]
        self.hiragana = hiragana # list[string]

    @staticmethod
    def from_dict(dict: dict):
        return QuizQuestion(
            dict['id'],
            dict['english'],
            dict['romanji'],
            dict['hiragana'])

    def get_question(self, question_language: str):
        match question_language:
            case 'english':
                return ' or '.join(self.english)
            case 'romanji':
                return ' or '.join(self.romanji)
            case 'hiragana':
                return ' or '.join(self.hiragana)
            case _:
                return None

    def get_answers(self, answer_language: str):
        match answer_language:
            case 'english':
                return self.english
            case 'romanji':
                return self.romanji
            case 'hiragana':
                return self.hiragana
            case _:
                return None


class QuizAttempt:
    def __init__(self, user_id: str, quiz_id: str, quiz_title: str, question_language: str, answer_language: str, score: float, responses: dict, date: str = None):
        self.user_id = user_id
        self.quiz_id = quiz_id
        self.quiz_title = quiz_title 
        self.date = date if date else datetime.today().strftime("%d/%m/%Y %H:%M:%S")
        self.question_language = question_language
        self.answer_language = answer_language
        self.score = score
        self.responses = responses # dict[question id, QuizResponse]

    @staticmethod
    def from_dict(dict: dict):
        return QuizAttempt(dict['user_id'], dict['quiz_id'], dict['quiz_title'], dict['question_language'], dict['answer_language'], dict['score'], {uq.question_id: uq for uq in [QuizResponse.from_dict(q) for q in dict['questions'].values()]}, dict['date'])

    def get_results(self):
        return [qq.get_result() for qq in self.responses.values()]

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'quiz_id': self.quiz_id,
            'quiz_title': self.quiz_title,
            'date': self.date,
            'question_language': self.question_language,
            'answer_language': self.answer_language,
            'score': self.score,
            'questions': {k: q.to_dict() for k,q in self.responses.items()}
        }

    def to_display_dict(self):
        quizAttempt = self.to_dict()
        quizAttempt['score'] = MiscUtils.format_percent(self.score)
        return quizAttempt


class QuizResponse:
    def __init__(self, question_id: str, question: str, answers: list, user_answer: str, correct: bool):
        self.question_id = question_id 
        self.question = question
        self.answers = answers
        self.user_answer = user_answer
        self.correct = correct

    @staticmethod
    def from_dict(dict: dict):
        return QuizResponse(dict['question_id'], dict['question'], dict['answers'], dict['user_answer'], dict['correct'])

    def get_result(self):
        data = self.to_dict()
        data['answers'] = str(' or '.join(self.answers))
        return data

    def to_dict(self):
        return self.__dict__

class LeaderboardRank:
    def __init__(self, place: int, user_id: str, user_name: str, count_quizzes: int, average_score: float):
        self.place = place
        self.user_id = user_id
        self.user_name = user_name
        self.count_quizzes = count_quizzes
        self.average_score = average_score

    def to_dict(self):
        return self.__dict__