from __future__ import unicode_literals, print_function
import plac
import codecs
import sys
import math

import spacy.en
from spacy.parts_of_speech import VERB, NOUN, ADV, ADJ

from termcolor import colored
from twython import TwythonStreamer

from os import path
from math import sqrt

from numpy import dot
from numpy.linalg import norm


class Meaning(object):
    def __init__(self, vectors):
        if vectors:
            self.vector = sum(vectors) / len(vectors)
            self.norm = norm(self.vector)
        else:
            self.vector = None
            self.norm = 0

    @classmethod
    def from_path(cls, nlp, loc):
        with codecs.open(loc, 'r', 'utf8') as file_:
            terms = file_.read().strip().split()
        return cls.from_terms(nlp, terms)

    @classmethod
    def from_tokens(cls, nlp, tokens):
        vectors = [t.repvec for t in tokens]
        return cls(vectors)

    @classmethod
    def from_terms(cls, nlp, examples):
        lexemes = [nlp.vocab[eg] for eg in examples]
        vectors = [eg.repvec for eg in lexemes]
        return cls(vectors)

    def similarity(self, other):
        if not self.norm or not other.norm:
            return -1
        return dot(self.vector, other.vector) / (self.norm * other.norm)


def print_colored(model, stream=sys.stdout):
    if model['is_match']:
        color = 'green'
    elif model['is_reject']:
        color = 'red'
    else:
        color = 'grey'
    
    if not model['is_rare'] and model['is_match'] and not model['is_reject']:
        match_score = colored('%.3f' % model['match_score'], 'green')
        reject_score = colored('%.3f' % model['reject_score'], 'red')
        prob = '%.5f' % model['prob']

        print(match_score, reject_score, prob)
        print(repr(model['text']), color)
        print('')


class TextMatcher(object):
    def __init__(self, nlp, get_target, get_reject, min_prob, min_match, max_reject):
        self.nlp = nlp
        self.get_target = get_target
        self.get_reject = get_reject
        self.min_prob = min_prob
        self.min_match = min_match
        self.max_reject = max_reject

    def __call__(self, text):
        tweet = self.nlp(text)
        target_terms = self.get_target()
        reject_terms = self.get_reject()

        prob = sum(math.exp(w.prob) for w in tweet) / len(tweet)
        meaning = Meaning.from_tokens(self, tweet)
        
        match_score = meaning.similarity(self.get_target())
        reject_score = meaning.similarity(self.get_reject())
        return {
            'text': tweet.string,
            'prob': prob,
            'match_score': match_score,
            'reject_score': reject_score,
            'is_rare': prob < self.min_prob,
            'is_match': prob >= self.min_prob  and match_score  >= self.min_match,
            'is_reject': prob >= self.min_prob and reject_score >= self.max_reject
        }


class Connection(TwythonStreamer):
    def __init__(self, keys_dir, handler, view):
        keys = Secrets(keys_dir)
        TwythonStreamer.__init__(self, keys.key, keys.secret, keys.token, keys.token_secret) 
        self.handler = handler
        self.view = view

    def on_success(self, data):
        text = data.get('text', u'')
        # Twython returns either bytes or unicode, depending on tweet.
        # #APIshaming
        try:
            model = self.handler(text)
        except TypeError:
            model = self.handler(text.decode('utf8'))
        status = self.view(model, sys.stdin)

    def on_error(self, status_code, data):
        print(status_code)


class Secrets(object):
    def __init__(self, key_dir):
        self.key = open(path.join(key_dir, 'key.txt')).read().strip()
        self.secret = open(path.join(key_dir, 'secret.txt')).read().strip()
        self.token = open(path.join(key_dir, 'token.txt')).read().strip()
        self.token_secret = open(path.join(key_dir, 'token_secret.txt')).read().strip()


def main(keys_dir, term, target_loc, reject_loc, min_prob=-20, min_match=0.8, max_reject=0.5):
    # We don't need the parser for this demo, so may as well save the loading time
    nlp = spacy.en.English(Parser=None)
    get_target = lambda: Meaning.from_path(nlp, target_loc)
    get_reject = lambda: Meaning.from_path(nlp, reject_loc)
    matcher = TextMatcher(nlp, get_target, get_reject, min_prob, min_match, max_reject)

    twitter = Connection(keys_dir, matcher, print_colored)
    twitter.statuses.filter(track=term)


if __name__ == '__main__':
    plac.call(main)