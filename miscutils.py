import os

class MiscUtils:
    @staticmethod
    def format_percent(n):
        return "{:.2f}%".format(float(n)*100)
