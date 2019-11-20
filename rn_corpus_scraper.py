#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2019 Jeremy Fahringer @jfahringer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#
# DISCLAIMER:
# Use of this scraper is subject to the terms and conditions of the Russian National Corpus available at http://ruscorpora.ru/new/corpora-usage.html
# Data extracted must abide by those terms.
#
# Usage: rn_corpus_scraper.py [-h] [--list LIST] [--resume RESUME]
#                             [--sleep SLEEP] [--limit LIMIT] [-i INPUT]
#                             [-o OUTPUT] [-v]
#
# Query Russian National Corpus for Keyword in Context (kwic) results and export
# to tab-separated file.
#
# optional arguments:
#   -h, --help            show this help message and exit
#   --list LIST           list of strings or tab-separated file containing list
#                         of words to query (related pairs on same line).
#   --resume RESUME       resume from word in list
#   --sleep SLEEP         rate limit new queries performed (delay in
#                         milliseconds)
#   --limit LIMIT         limit number of queries performed
#   -i INPUT, --input INPUT
#                         use saved input directory
#   -o OUTPUT, --output OUTPUT
#                         output directory
#   -v, --verbose         verbose printing
#
# Install:
# pip install requests bs4 lxml


# Built-in modules:
import re
import json
import unicodedata
import csv
import time
import argparse
import os.path
import itertools

# Third-party modules provided by Anaconda:
import requests
import bs4		# also requires parser 'lxml' to be installed

# RNC query word list
# use a nested array to include set ordering, otherwise use a flat array of strings
word_pairs = [
				["тест", "речь"],
				["еда", "питание"],
			]

# Russian National Corpus query parameters
rnc_query_url = "http://processing.ruscorpora.ru/search.xml?sort=i_grtagging&lang=ru&lex1="
rnc_query_lex1 = "конфликт"
rnc_query_params = "&startyear=1984&text=lexgramm&max1=1&sem-mod2=sem&sem-mod2=sem2&gramm1=S,(nom%7Cvoc%7Cgen%7Cgen2%7Cdat%7Cacc%7Cacc2%7Cins%7Cloc%7Cloc2%7Cadnum)&sem-mod1=sem&sem-mod1=sem2&level1=0&level2=0&endyear=2019&parent2=0&parent1=0&min1=1&out=kwic&nodia=1&mode=main&p="
rnc_query_page = 1
rnc_query_page_offset = -1
rnc_query_startyear = "1900"
rnc_query_endyear = "2019"
rnc_query_paged_template = "http://processing.ruscorpora.ru/search.xml?sort=i_grtagging&lang=ru&lex1={lex}&startyear=" + rnc_query_startyear + "&text=lexgramm&max1=1&sem-mod2=sem&sem-mod2=sem2&gramm1=S,(nom%7Cvoc%7Cgen%7Cgen2%7Cdat%7Cacc%7Cacc2%7Cins%7Cloc%7Cloc2%7Cadnum)&sem-mod1=sem&sem-mod1=sem2&level1=0&level2=0&endyear=" + rnc_query_endyear + "&parent2=0&parent1=0&min1=1&out=kwic&nodia=1&mode=main&p={page}"
rnc_strip_characters = ' -—―,;:!?."“«»()[]/%<>'

input_dir = "input/"
output_dir = "output/"
headers = ["precontext", "preceding", "kwic", "following", "postcontext", "metadata", "date"]
header_text = {
				"precontext": "PRE_CONTEXT",
				"preceding": "PRECEDING_WORD",
				"kwic": "KWIC",
				"following": "FOLLOWING_WORD",
				"postcontext": "POST_CONTEXT",
				"metadata": "METADATA",
				"date": "DATE"}

rate_limit = 200  # milliseconds
default_max_limit = 200000  # default limit for queries performed
response_time = 0  # save last response time for backing off
verbose = False  # verbose printing

# queues for visiting pages
# pages to visit
pages_queue = {}
# pages queried
pages_queried = {}

# set up verboseprint as a function if verbose printing is set
verboseprint = print if verbose else lambda *a, **k: None


def get_rnc_html(rnc_lex, rnc_page, rnc_set=0, use_new=False):
	global response_time
	filename = "RNC_{lex}_{page}.html".format(lex=rnc_lex, page=rnc_page)
	filename_withset = "RNC_{set}_{lex}_{page}.html".format(set=rnc_set, lex=rnc_lex, page=rnc_page)

	if rnc_lex not in pages_queue or pages_queue[rnc_lex] is None:
		pages_queue[rnc_lex] = []
	if rnc_lex not in pages_queried or pages_queried[rnc_lex] is None:
		pages_queried[rnc_lex] = []

	if not use_new:
		try:
			if os.path.isfile(input_dir + filename_withset):
				f = open(input_dir + filename_withset)
				used_filename = filename_withset
			else:
				f = open(input_dir + filename)
				used_filename = filename
		except OSError as err:
			pass
		else:
			text = f.read()
			f.close()
			verboseprint("Using saved file " + used_filename)
			if rnc_lex in pages_queue and rnc_page in pages_queue[rnc_lex]:
				pages_queue[rnc_lex].remove(rnc_page)
			if rnc_lex in pages_queried and rnc_page not in pages_queried[rnc_lex]:
				pages_queried[rnc_lex].append(int(rnc_page))

			return text

#   fetch new html data and write it to input_dir
	if response_time > 0:
		rate_ms = rate_limit / 1000
		delay_time = rate_ms + 2*response_time
		verboseprint("Waiting for ", str(delay_time), "s; response time :", str(response_time))
		time.sleep(delay_time)
	else:
		verboseprint("Rate limit for ", str(rate_limit), " milliseconds.")
		time.sleep(rate_limit / 1000)

	verboseprint("Requesting query page for " + rnc_lex + " page " + str(rnc_page))
	t0 = time.time()
	# get RNC html raw page using the visual page number, not the p= query value
	rnc_html = requests.get(rnc_query_paged_template.format(lex=rnc_lex, page=rnc_page + rnc_query_page_offset)).text
	response_time = time.time() - t0

	if rnc_lex in pages_queried:
		pages_queried[rnc_lex].append(rnc_page)
	else:
		pages_queried[rnc_lex] = [rnc_page]
	verboseprint(" ".join(["added to pages queried:", rnc_lex, str(rnc_page)]))

	if rnc_lex in pages_queue and rnc_page in pages_queue[rnc_lex]:
		pages_queue[rnc_lex].remove(rnc_page)
		verboseprint(" ".join(["removed from page queue:", rnc_lex, str(rnc_page)]))

	try:
		f = open(input_dir + filename, "w")
		f.write(rnc_html)
		f.close()
	except OSError as err:
		verboseprint("OS error: {0}".format(err))
		print("Could not save html file for " + rnc_lex + " page " + str(rnc_page))

	return rnc_html


def get_rnc_text_table(rnc_html_raw):
	rnc_html = bs4.BeautifulSoup(rnc_html_raw, "lxml")
	rnc_tables = rnc_html.find_all("table")

	if rnc_tables is None or len(rnc_tables) is 0:
		return ""

	for table in rnc_tables:
		if len(table.find_all("table")) > 0:
			# find the table that contains more tables, where the keyword in context results live
			# assumption: there is only 1 table with nested tables.
			# If this assumption is not true, the first nesting table will be returned
			return table

	return ""
#     return rnc_tables ## returns all tables, which is not a good failure mode


def get_rnc_rows(rnc_table, attr=headers):
	#    find the content for each row
	#    select sections by attributes in the rnc_row
	if rnc_table is "":
		rows = [{"kwic": "RNC_NOT_FOUND", }]
		return rows

	rnc_rows = rnc_table.find_all("tr", recursive=False)
	if rnc_rows is None or len(rnc_rows) == 0:
		# if no <tr> elements, check for an <ol> element in rnc_table first
		rnc_rows = rnc_table.find("ol").find_all("tr", recursive=False)

	rows = []

	if rnc_rows is not None and len(rnc_rows) > 0:
		for row in rnc_rows:
			selectdict = {}
			tds = row.find_all("td", recursive=False)
			for i, td in enumerate(tds):
				# counting of td elements is abnormal because of nested table structure and find_all("td")
				if i == 0 and ("precontext" in attr or "preceding" in attr):
					if "precontext" in attr and "precontext" not in selectdict:
						selectdict['precontext'] = unicodedata.normalize("NFKD", td.text).strip()
					if "preceding" in attr and "preceding" not in selectdict:
						selectdict['preceding'] = unicodedata.normalize("NFKD", td.text).strip(rnc_strip_characters).strip().split(" ")[-1]
				elif i == 1 and "kwic" in attr:
					selectdict['kwic'] = unicodedata.normalize("NFKD", td.text).strip()
				elif i == 2 and ("postcontext" in attr or "following" in attr):
					spans = td.find_all("span")
					post_text = " ".join([span.text for span in spans]).strip()
					if "following" in attr and "following" not in selectdict:
						selectdict['following'] = post_text.strip(rnc_strip_characters).strip().split(" ")[0]
					if "postcontext" in attr and "postcontext" not in selectdict:
						selectdict['postcontext'] = post_text

				if i == 2 and ("metadata" in attr or "date" in attr):
					# assume that <a> is <a class="b-kwic-expl">
					verboseprint(td.a["msg"])
					metadata = td.a["msg"].strip()
					if len(metadata) < 1:
						metadata = 'RNC_UNSPECIFIED'
					if "metadata" in attr:
						selectdict['metadata'] = metadata
					if "date" in attr:
						date = re.search(r'\d{4}', metadata)
						if date is None:
							date = 'RNC_UNSPECIFIED'
						else:
							date = date.group(0)
						selectdict['date'] = date
			rows.append(selectdict)
		return rows

	return []


def get_rnc_next_pages(rnc_html_raw, rnc_lex, current_page=1):
	rnc_soup = bs4.BeautifulSoup(rnc_html_raw, "html.parser")
	rnc_pager = rnc_soup.find("p", {"class": "pager"})
	if rnc_pager is None:
		return []
	rnc_pages = rnc_pager.find_all("a")
	# only return next pages, not pages prior to current_page
	pages = [int(page.text) for page in rnc_pages if (page.text.isdigit() and int(page.text) > current_page)]

	if rnc_lex in pages_queue:
		if pages_queue[rnc_lex] is None:
			pages_queue[rnc_lex] = []
		pages_queue[rnc_lex] = sorted(list(set(pages_queue[rnc_lex] + pages)))
	else:
		pages_queue[rnc_lex] = pages
	return pages


def save_rnc_to_tsv(rnc_set, rnc_lex, rnc_rows, keys=headers):
	filename = "RNC_{set}_{lex}.tsv".format(set=rnc_set, lex=rnc_lex)
	try:
		output_file = open(output_dir + filename, 'w')
		dict_writer = csv.DictWriter(output_file, keys, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL, extrasaction="ignore")
		dict_writer.writeheader()
		dict_writer.writerows(rnc_rows)
		output_file.close()
		print("Saved " + str(len(rnc_rows)) + " rows to " + filename)
		return True
	except OSError as err:
		verboseprint("OS error: {0}".format(err))
		print("Could not save tsv file for " + rnc_lex + " to " + output_dir + filename)
	return False


def main(word_list=word_pairs, resume_lex="", sleep=rate_limit, max_limit=default_max_limit, verbose=False, **kwargs):
	global rate_limit
	if verbose:
		verbose = True

	verboseprint = print if verbose else lambda *a, **k: None

	# clean up sleep and max_limit integers
	if sleep <= 0:
		rate_limit = 0
	else:
		rate_limit = sleep
	if max_limit <= 0:
		max_limit = default_max_limit

	total_queries = 0
	if resume_lex is "":
		begin = True
	else:
		begin = False

	for i_set, word_set in enumerate(word_list):
		verboseprint("Processing set ", str(i_set), word_set)
		verboseprint("Query max limit :", str(max_limit), "\t total queries so far : ", str(total_queries))
		if isinstance(word_set, str):
			# if word_set is actually a word, make it into a 1-length list
			word_set = [word_set]

		for word in word_set:
			if resume_lex == word:
				verboseprint("Resume processing at", resume_lex)
				begin = True
			if begin:
				rows = []
				pages_queue[word] = [rnc_query_page]
				while len(pages_queue[word]) > 0 and (max_limit is 0 or total_queries <= max_limit):
					query_page = pages_queue[word].pop(0)
					current_html = get_rnc_html(word, query_page, rnc_set=i_set)
					get_rnc_next_pages(current_html, word, query_page)
					current_table = get_rnc_text_table(current_html)
					current_rows = get_rnc_rows(current_table)
					if len(current_rows) > 0:
						rows = rows + current_rows
					total_queries += 1
				save_rnc_to_tsv(i_set, word, rows)
			if total_queries >= max_limit:
				print("Stopped after ", str(total_queries), " queries.")
				begin = False


def process_user_directories(input="", output="", **kwargs):
	global input_dir
	global output_dir

	if input is not "" and os.path.isdir(input):
		if not input.endswith("/"):
			input_dir = input + "/"
		else:
			input_dir = input
	if output is not "" and os.path.isdir(output):
		if not output.endswith("/"):
			output_dir = output + "/"
		else:
			output_dir = output
	# try to make directories if they're not made yet
	os.makedirs(input_dir, exist_ok=True)
	os.makedirs(output_dir, exist_ok=True)
	verboseprint("input directory:\t" + input_dir)
	verboseprint("output directory:\t" + output_dir)
	return {
			"input_dir": input_dir,
			"output_dir": output_dir
			}


def process_user_list(input_list="", **kwargs):
	word_list = []
	if input_list is not "" and os.path.isfile(input_list):
		try:
			list_file = open(input_list, 'r', newline="")
			dialect = csv.Sniffer().sniff(list_file.read(1024))
			list_file.seek(0)
			dict_reader = csv.reader(list_file, dialect)  # , delimiter='\t', quotechar='"'
			dict_list = list(dict_reader)
			if len(dict_list) > 0:
				for row in dict_list:
					while ("" in row):
						row.remove("")
					if len(row):
						word_list.append(row)
			else:
				print("No words to query found in " + input_list)
			list_file.close()
			verboseprint("Read " + str(len(word_list)) + " rows from " + input_list)
		except OSError as err:
			verboseprint("OS error: {0}".format(err))
			print("Could not read tsv file from " + filename)
	elif input_list is not "":
		string_list = input_list.splitlines()
		if len(string_list) == 1:
			# if string isn't split by lines, try splitting by ",", then finding all sets of word characters [\w]+
			string_list = input_list.split(",")
			if len(string_list) == 1:
				word_list = re.findall(r"[\w]+", string_list[0])
				while ("" in word_list):
					word_list.remove("")
			else:
				for words in string_list:
					words = re.findall(r"[\w]+", words)
					while ("" in words):
						words.remove("")
					word_list.append(words)
		elif len(string_list) > 1:
			for line in string_list:
				words = re.findall(r"[\w]+", line)
				while ("" in words):
					words.remove("")
				word_list.append(words)

	if len(word_list) is 0 and len(word_pairs) > 0:
		word_list = word_pairs
	elif len(word_list) is 0 and len(word_pairs) > 0:
		print("No words to query.")
		return []

	print("Word list to query:")
	print('\t','\n\t'.join(['\t'.join([str(word) for word in row]) for row in word_list]))
	return word_list


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Query Russian National Corpus for Keyword in Context (kwic) results and export to tab-separated file.")
	parser.add_argument("--list", type=str, default="", help="list of strings or tab-separated file containing list of words to query (related pairs on same line).")
	parser.add_argument("--resume", type=str, default="", help="resume from word in list")
	parser.add_argument("--sleep", type=int, default=300, help="rate limit new queries performed (delay in milliseconds)")
	parser.add_argument("--limit", type=int, default=default_max_limit, help="limit number of queries performed")
	parser.add_argument("-i", "--input", type=str, default=input_dir, help="use saved input directory")
	parser.add_argument("-o", "--output", type=str, default=output_dir, help="output directory")
	parser.add_argument("-v", "--verbose", action='store_true', help="verbose printing")

	args = parser.parse_args()

	verbose = True if args.verbose is not False else False
	verboseprint = print if verbose else lambda *a, **k: None

	directories = process_user_directories(input=args.input, output=args.output)
	word_list = process_user_list(args.list)
	flat_list = list(itertools.chain(*word_list))
	if args.resume is not "" and args.resume not in flat_list:
		# don't do anything if resume word is not in the list of words to query
		print("Could not find 'resume' word " + str(args.resume) + " in query list")
	elif args.resume is not "":
		main(word_list=word_list, resume_lex=args.resume, sleep=args.sleep, max_limit=args.limit, verbose=verbose)
	else:
		main(word_list=word_list, sleep=args.sleep, max_limit=args.limit, verbose=verbose)
