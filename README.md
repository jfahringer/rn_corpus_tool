# Russian National Corpus scraper
A tool to save the results of Russian National Corpus keyword-in-context queries for scientific research.


## Disclaimer
This tool comes with NO WARRANTY of any kind and is licensed under GNU General Public License v3.0.

Use of this scraper is subject to the terms and conditions of the Russian National Corpus available at http://ruscorpora.ru/new/corpora-usage.html
Data extracted must abide by those terms.


## Citation format

Fahringer, J. 2019a, Russian National Corpus scraper: A tool to save the results of Russian National Corpus keyword-in-context queries, v1.0.0, Zenodo, doi:10.5281/zenodo.3548846

[![DOI](https://zenodo.org/badge/222530191.svg)](https://zenodo.org/badge/latestdoi/222530191)


## Usage
<pre>
 rn_corpus_scraper.py [-h] [--list LIST] [--resume RESUME]
                            [--sleep SLEEP] [--limit LIMIT] [-i INPUT]
                            [-o OUTPUT] [-v]
</pre>

Query Russian National Corpus for Keyword in Context (kwic) results and export
to tab-separated file.

## optional arguments
<pre>
  -h, --help            show this help message and exit
  --list LIST           list of strings or tab-separated file containing list
                        of words to query (related pairs on same line).
  --resume RESUME       resume from word in list
  --sleep SLEEP         rate limit new queries performed (delay in
                        milliseconds)
  --limit LIMIT         limit number of queries performed
  -i INPUT, --input INPUT
                        use saved input directory
  -o OUTPUT, --output OUTPUT
                        output directory
  -v, --verbose         verbose printing
</pre>

## install
```
pip install requests bs4 lxml
```
