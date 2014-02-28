#!/usr/bin/env python -OO
# -*- coding: utf-8 -*-


from __future__ import with_statement
from glob import glob
import argparse, re, os, sys, sqlite3, datetime
from bs4 import BeautifulSoup
import HTMLParser

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jeopardy.settings")
sys.path.append('../')
import jeopardyapp.models as models

h = HTMLParser.HTMLParser()



def main(args):
    """Loop thru all the games and parse them."""
    if not os.path.isdir(args.dir):
        print "The specified folder is not a directory."
        sys.exit(1)
    NUMBER_OF_FILES = len(os.listdir(args.dir))
    if args.num_of_files:
        NUMBER_OF_FILES = args.num_of_files
    print "Parsing", NUMBER_OF_FILES, "files"

    for i, file_name in enumerate(glob(os.path.join(args.dir, "*.html")), 1):
        with open(os.path.abspath(file_name)) as f:
            parse_game(f, i)
    # if not args.stdout:
    #     sql.commit()
    print "All done"


def parse_game(f, gid):
    """Parses an entire Jeopardy! game and extract individual clues."""
    bsoup = BeautifulSoup(f, "lxml")
    # the title is in the format:
    # J! Archive - Show #XXXX, aired 2004-09-16
    # the last part is all that is required

    airdate = datetime.datetime.strptime(bsoup.title.get_text().split()[-1], '%Y-%m-%d').date()

    #TODO remove the fake stuff below
    season = models.Season.objects.get(pk=1)
    episode = models.Episode(date=airdate, show_number=1, season=season)
    episode.save()

    if not parse_round(bsoup, 1, gid, episode) or not parse_round(bsoup, 2, gid, episode):
        # one of the rounds does not exist
        pass


    # the final Jeopardy! round
    r = bsoup.find("table", class_="final_round")
    if not r:
        # this game does not have a final clue
        return
    category_name = h.unescape(r.find("td", class_="category_name").get_text())
    try:
        category = models.Category.objects.get(category_name=category_name)
    except models.Category.DoesNotExist:
        category = models.Category(category_name=category_name)
        category.save()
    final_round_obj = models.Round.objects.get(order=3)
    episode_category = models.EpisodeCategory(
        episode=episode,
        category=category,
        round=final_round_obj,
        order=1
    )
    episode_category.save()

    text = r.find("td", class_="clue_text").get_text()
    answer = BeautifulSoup(r.find("div", onmouseover=True).get("onmouseover"), "lxml")
    answer = answer.find("em").get_text()
    # False indicates no preset value for a clue
    #insert([gid, airdate, 3, category, False, text, answer])

    question = models.Question(
        answer=text,
        question=answer,
        value=0,
        episode_category=episode_category,
        daily_double=False
    )
    question.save()


def parse_round(bsoup, rnd, gid, episode):

    """Parses and inserts the list of clues from a whole round."""
    round_obj = models.Round.objects.get(order=rnd)
    round_id = "jeopardy_round" if round_obj.order == 1 else "double_jeopardy_round"
    r = bsoup.find(id=round_id)

    # the game may not have all the rounds
    if not r:
        return False

    # the list of categories for this round
    category_names = [c.get_text() for c in r.find_all("td", class_="category_name")]

    # the list of category objects for categories in this round
    episode_categories = []
    for index, category_name in enumerate(category_names):

        category_name = h.unescape(category_name)
        try:
            category = models.Category.objects.get(category_name=category_name)
        except models.Category.DoesNotExist:
            category = models.Category(category_name=category_name)
            category.save()

        episode_category = models.EpisodeCategory(
            episode=episode,
            category=category,
            round=round_obj,
            order=index + 1
        )
        episode_category.save()
        episode_categories.append(episode_category)

    # the x_coord determines which category a clue is in
    # because the categories come before the clues, we will
    # have to match them up with the clues later on
    x = 0
    for a in r.find_all("td", class_="clue"):
        if not a.get_text().strip():
            continue
        value = a.find("td", class_=re.compile("clue_value")).get_text().lstrip("D: $")
        text = a.find("td", class_="clue_text").get_text()
        answer = BeautifulSoup(a.find("div", onmouseover=True).get("onmouseover"), "lxml")
        answer = answer.find("em", class_="correct_response").get_text()

        # insert([gid, airdate, rnd, categories[x], value, text, answer])

        question = models.Question(
            answer=text,
            question=answer,
            value=value.replace(',', ''),
            episode_category=episode_categories[x],
            daily_double=False
        )
        question.save()


        # always update x, even if we skip
        # a clue, as this keeps things in order. there
        # are 6 categories, so once we reach the end,
        # loop back to the beginning category
        #
        # x += 1
        # x %= 6
        x = 0 if x == 5 else x + 1
    return True


def insert(clue):
    """Inserts the given clue into the database."""
    raise NotImplemented

    # clue is [game, airdate, round, category, value, clue, answer]
    # note that at this point, clue[4] is False if round is 3
    # if "\\\'" in clue[6]:
    #     clue[6] = clue[6].replace("\\\'", "'")
    # if "\\\"" in clue[6]:
    #     clue[6] = clue[6].replace("\\\"", "\"")
    # if not sql:
    #     print clue
    #     return

    # sql.execute("INSERT OR IGNORE INTO airdates VALUES(?, ?);", (clue[0], clue[1], ))
    # sql.execute("INSERT OR IGNORE INTO categories(category) VALUES(?);", (clue[3], ))
    # category_id = sql.execute("SELECT id FROM categories WHERE category = ?;", (clue[3], )).fetchone()[0]
    # clue_id = sql.execute("INSERT INTO documents(clue, answer) VALUES(?, ?);", (clue[5], clue[6], )).lastrowid
    # sql.execute("INSERT INTO clues(game, round, value) VALUES(?, ?, ?);", (clue[0], clue[2], clue[4], ))
    # sql.execute("INSERT INTO classifications VALUES(?, ?)", (clue_id, category_id, ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse games from the J! Archive website.",
        add_help=False,
        usage="%(prog)s [options]"
    )
    parser.add_argument(
        "-d", "--dir",
        dest="dir",
        metavar="<folder>",
        help="the directory containing the game files",
        default="j-archive"
    )
    parser.add_argument(
        "-n", "--number-of-files",
        dest="num_of_files",
        metavar="<number>",
        help="the number of files to parse",
        type=int
    )
    parser.add_argument(
        "-f", "--filename",
        dest="database",
        metavar="<filename>",
        help="the filename for the SQLite database",
        default="clues.db"
    )
    parser.add_argument(
        "--stdout",
        help="output the clues to stdout and not a database",
        action="store_true"
    )
    parser.add_argument("--help", action="help", help="show this help message and exit")
    parser.add_argument("--version", action="version", version="2013.07.09")
    main(parser.parse_args())
