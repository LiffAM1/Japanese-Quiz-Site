import os
import time
import json
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from model.models import *

class FirestoreRepo:
    def __init__(self, collection):  
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        self.db = firestore.client()
        self.collection = self.db.collection(collection)

    def query(self, field, operation, val): 
        docs = self.collection.where(filter=FieldFilter(field, operation, val)).stream()
        return [doc.to_dict() for doc in docs]

    def get(self, filename): 
        res = self.collection.document(filename)
        if res:
            doc = res.get().to_dict()
            return doc
        else:
            return None

    def get_all(self):
        docs = self.collection.get()
        return [doc.to_dict() for doc in docs]

    def save(self, filename, data): 
        self.collection.document(filename).set(data)

# Model repos
class UsersRepo(FirestoreRepo):
    def __init__(self):
        super().__init__("users")

    def get(self, user_id: str):
        user = super().get(user_id)
        if user:
            return User.from_dict(user)
        return None

    def get_all(self):
        return [User.from_dict(u) for u in super().get_all()]

    def save(self, user: User):
        data = user.to_dict()
        super().save(user.id, data)

    def set_active(self, user_id: str):
        user = self.get(user_id)
        if user:
            user.is_active = True
            user.is_authenticated = True
            self.save(user)

    def set_inactive(self, user_id: str):
        user = self.get(user_id)
        if user:
            user.is_active = False
            user.is_authenticated = False 
            self.save(user)

class QuizAttemptsRepo(FirestoreRepo):
    def __init__(self):
        super().__init__("quiz_attempts")

    def get_all_for_user(self, user_id: str):
        return [QuizAttempt.from_dict(qa) for qa in super().query('user_id',"==", user_id)]

    def get_all_for_quiz(self, quiz_id: str):
        return [QuizAttempt.from_dict(qa) for qa in super().query('quiz_id',"==", quiz_id)]

    def save(self, attempt: QuizAttempt):
        data = attempt.to_dict()
        super().save(attempt.quiz_id + "-" + attempt.user_id + '-' + str(time.time()), json.loads(json.dumps(data)))

class QuizzesRepo(FirestoreRepo):
    def __init__(self):
        super().__init__("quizzes")
        self.seed()

    def get(self, quiz_id: str):
        quiz = super().get(quiz_id)
        if quiz:
            return Quiz.from_dict(quiz)

    def get_all(self):
        return [Quiz.from_dict(q) for q in super().get_all()]

    def save(self, quiz: Quiz):
        data = quiz.to_dict()
        super().save(quiz.id, data)

    def seed(self):
        path = 'quizzes'
        for filename in os.listdir(path):
            file = os.path.join(path, filename)
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
                quiz = self.get(data['id'])
                if not quiz:
                    super().save(data['id'], data)
