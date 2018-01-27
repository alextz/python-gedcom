# -*- coding: utf8 -*-
#
# Gedcom 5.5 Parser
#
# Copyright (C) 2012 Madeleine Price Ball
# Copyright (C) 2005 Daniel Zappala (zappala [ at ] cs.byu.edu)
# Copyright (C) 2005 Brigham Young University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# Please see the GPL license at http://www.gnu.org/licenses/gpl.txt
#
# This code based on work from Zappala, 2005.
# To contact the Zappala, see http://faculty.cs.byu.edu/~zappala

#
#
#       October 2, 2017         bar     fix index errors when getting marriage/birth/death years
#       October 4, 2017         bar     family_search_id()
#       October 6, 2017         bar     ignore blank lines
#       October 29, 2017        bar     afn()
#                                       compile the line regex and expose it
#                                       main()
#       November 3, 2017        bar     fix_date_year()
#                                       return -1 instead of empty string for non-individuals' birth/death years
#                                       uid(), refn(), mh_rin() - empty string from string functions if not individual or not found
#                                       able to handle utf8 3-byte leader at the top of the file
#                                       regx now allows line of file to not have a \r or \n at the end - for the last line in the file
#       November 6, 2017        bar     clean up code
#                                       fix a recent typo
#                                       fix a disagreement betweeen multiple 'return' values in birth() and death()
#                                       fix wrong return value in private() and occupation() when not an individual
#       November 7, 2017        bar     various changes noted from pull requests on github search for "github:"
#                                       reverse get-name logic to use GIVN/SURN values before using the NAME value
#                                       strip a lot of values when they are used in case they have spaces
#                                       find_path_to_anc() has a parent-type parameter and defaults to finding ALL parents rather than NAT parents
#       December 25, 2017       bar     get_children()
#       January 12, 2018        bar     de-dupe birth/marriage/death date code
#                                       better date parsing - a_date()
#       January 13, 2018        bar     bfr for before and many others
#       January 14, 2018        bar     more date parsing details
#       January 19, 2018        bar     yyyymmdd/mmddyyyy and such - go with 1300+ years first, figuring years in this form won't be earlier than 1300.
#
#


# Global imports
from    __future__  import  print_function
import  difflib
import  re
import  string
import  sys


ged_line_re = re.compile(
    # Level must start with nonnegative int, no leading zeros.
    '^(0|[1-9]+[0-9]*) ' +
    # Pointer optional, if it exists it must be flanked by '@'
    '(@[^@]+@ |)' +
    # Tag must be alphanumeric string
    '([A-Za-z0-9_]+)' +
    # Value optional, consists of anything after a space to end of line
    '( [^\n\r]*|)' +
    # End of line defined by \n or \r
    '([\r\n]{1,2}|$)'                     # github:mtdcr to be able to output the exact same file as input. That requires open(mode = 'rb'), which opens another can of worms. P2, for instance, puts the CR in \n\r at the front of the next line. And don't let's start on the encoding and 'newline'.
    )


import  unicodedata
try :
    from    types   import ListType, TupleType, UnicodeType, DictionaryType
    bytes           = str
except ImportError :
    ListType        = list
    TupleType       = tuple
    UnicodeType     = str
    DictionaryType  = dict
    unicode         = str
    basestring      = str

def convert_to_unicode(s) :
    """ Try to convert the given string to unicode as best we can guess. """
    if  not isinstance(s, UnicodeType) :
        try :
            s   = unicode(s.decode('utf8'))     # this blows up on most latin1 chars - so we hope such is the case if the string is latin 1
        except UnicodeDecodeError :
            s   = unicode(s.decode('latin1'))   # bail out
        pass
    return(s)

def best_ascii(unicode_s) :
    """
        Return the best guess as to ASCII characters that could be used for the given string.
    """

    unicode_s   = convert_to_unicode(unicode_s)

    #
    #   NFKD doesn't work for a lot of characters \u0189, for instance, should be a D
    #   http://www.unicode.org/reports/tr36/confusables.txt is a tiny attempt at look-alikes.
    #   Best to do something to actually render characters in various fonts and compare them to ASCII chars in the same font.
    #   And this logic could be used to compare fonts and put them in family/groups.
    #
    #   Another way of dealing with this is to get the descriptions of the characters, unicodedata.name(c), from http://www.unicode.org/Public/UNIDATA/UnicodeData.txt, and do a least-differencs string thing against the ascii characters' names
    #   Some of the non-Roman names could be table-translated going in to such a thing.
    #
    #   Another thing to do would be to convert Chinese characters to Pingyen. And do similar to other appropriate languages.
    #
    s   = "".join([ unicodedata.normalize("NFKD", c)[0] for c in unicode_s ])

    return(s)




days_in_months  = [ 0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, ]    # look at your knuckles and the on-hand valleys between them


month_names = [
                [   'january',  'february',  'march',  'april',  'may',     'june',     'july',     'august', 'september',  'october', 'november',  'december',  ],
                [   'gennaio',  'febbraio',  'marzo',  'aprile', 'maggio',  'giugno',   'luglio',   'agosto', 'settembre',  'ottobre', 'novembre',  'dicembre',  ],
                [   'januar',   'februar',   'märz',   'april',  'mai',     'juni',     'juli',     'august', 'september',  'oktober', 'november',  'dezember',  ],
                [   'janeiro',  'fevereiro', 'março',  'abril',  'maio',    'junho',    'julho',    'agosto', 'setembro',   'outubro', 'novembro',  'dezembro',  ],
                [   'enero',    'febrero',   'marzo',  'abril',  'mayo',    'junio',    'julio',    'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre', ],
                [   'janvier',  'février',   'mars',   'avril',  'mai',     'juin',     'juillet',  'août',   'septembre',  'octobre', 'novembre',  'décembre',  ],
              ]
month_names =   [ [ best_ascii(mn) for mn in mns ] for mns in month_names ]


def str_ratio(nm1, nm2) :
    """ Return a number that reflects how well the 1st name matches the second. The higher the number, the more matchee they are. """
    nm1 = nm1.lower()
    nm2 = nm2.lower()
    all = difflib.SequenceMatcher(None, nm1,      nm2     ).ratio()
    sta = difflib.SequenceMatcher(None, nm1[:3 ], nm2[:3 ]).ratio()
    if  min(len(nm1), len(nm2)) < 6 :
        return (all + (sta * 2.0)) / 3.0
    end = difflib.SequenceMatcher(None, nm1[-3:], nm2[-3:]).ratio()
    return (all + (sta * 4.0) + (end * 2.0)) / 7.0


HELPP   = ""            # "":no_print   "\n":print_CRLF     else:print_no_CRLF

def best_month(name) :
    """ Return our best guess (1..12) as to what month the named month is. Zero means we don't know. """
    name       = best_ascii((name or '').lower())
    bm      = -1
    bd      = 0.0
    mh      = 0.0
    if  name   :
        for mnms in month_names :
            if  len(name) >= 3 :
                ma  = [ mi for mi, mn in enumerate(mnms) if mn.startswith(name) ]
                if  len(ma) == 1 :
                    d       = len(name)
                    if  bd  < d :
                        bd  = d                 # if the whole given name (3 letters or longer) starts a month name, give the month the score of the length of the name
                        bm  = ma[0]
                        mh  = 1.0               #    for debugging printout
                        break                   #    and be done with it - none of our names start ambiguously - june/july are the closest
                    pass
                pass
            mds = [ [ str_ratio(name, mn), mi, ] for mi, mn in enumerate(mnms) ]
            mds.sort()
            h   = mds[-1][0]
            # print(" >" + str(mds[-2:]) + "< " + str(h) + " " + str(h - mds[-2][0]))
            if  h >= 0.7    :
                d   = h - mds[-2][0]
                if  d >= 0.2    :
                    if  bd  < d :               # to find the language, find the best month in the list of months that's the most different from the 2nd best in that language
                        bd  = d
                        bm  = mds[-1][1]
                    pass
                pass
            mh  = max(mh, h)
        if  HELPP :
            print("@@@@ mh name", mh, bd, bm + 1, "[" + name + "]", end = "")
            if  HELPP == '\n' :
                print("")
            pass
        pass
    return bm + 1


dres            = r'(?:0[1-9]|[12]\d|3[0-1])'
any_dres        = r'(?:' + dres + r'|[1-9])'
mres            = r'(?:0[1-9]|1[0-2])'
any_mres        = r'(?:' + mres + r'|[1-9])'
yres            = r'(?:20[012][0-9]|[01]\d\d\d)'
any_yres        = r'(?:' + yres + r'|[01]?\d?\d?\d)'
Yres            = r'(?:20[012][0-9]|[1][3-9]\d\d)'          # years past 1300 - we could pass a list of recently found years to parse() and let each of them vote between ambiguous years' parses - or pass near-relatives' dates - or something
dres            = r'(' +     dres + r')'
any_dres        = r'(' + any_dres + r')'
mres            = r'(' +     mres + r')'
any_mres        = r'(' + any_mres + r')'
yres            = r'(' +     yres + r')'
any_yres        = r'(' + any_yres + r')'
Yres            = r'(' +     Yres + r')'

mn_res          = r'([a-z]{3,%u})'  % (max([ max([ len(mn) for mn in mns ]) for mns in month_names ]) + 1)      # +1 to let them mistype an extra character, worst case

slres           = r'\s*\/\s*'
dtres           = r'\s*\.\s*'
brres           = r'\s*\-\s*'

d_mnm_y_re      = re.compile(r'(?:^|[^\d])'  + any_dres + r'\s*'    + mn_res                                + r'[\s,\.]*'   + any_yres  + r'(?:[^\d]|$)',       re.IGNORECASE)
mnm_d_re        = re.compile(r'(?:^|[^a-z])'                        + mn_res                                + r'[\s,\.]*'   + any_dres  + r'(?:[^\d]|$)',       re.IGNORECASE)
mnm_y_re        = re.compile(r'(?:^|[^a-z])'                        + mn_res                                + r'[\s,\.]*'   + any_yres  + r'(?:[^\d]|$)',       re.IGNORECASE)
mnm_d_y_re      = re.compile(r'(?:^|[^a-z])'                        + mn_res   + r'[\s\.]*'     + any_dres  + r'[\s,]+'     + any_yres  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmddYYyy_re     = re.compile(r'(?:^|[^\d])'  + mres                 + dres                      + Yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ddmmYYyy_re     = re.compile(r'(?:^|[^\d])'  + dres                 + mres                      + Yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmddyyyy_re     = re.compile(r'(?:^|[^\d])'  + mres                 + dres                      + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ddmmyyyy_re     = re.compile(r'(?:^|[^\d])'  + dres                 + mres                      + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmsddsyyyy_re   = re.compile(r'(?:^|[^\d])'  + any_mres + slres     + any_dres + slres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ddsmmsyyyy_re   = re.compile(r'(?:^|[^\d])'  + any_dres + slres     + any_mres + slres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmDddDyyyy_re   = re.compile(r'(?:^|[^\d])'  + any_mres + dtres     + any_dres + dtres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ddDmmDyyyy_re   = re.compile(r'(?:^|[^\d])'  + any_dres + dtres     + any_mres + dtres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmBddByyyy_re   = re.compile(r'(?:^|[^\d])'  + any_mres + brres     + any_dres + brres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ddBmmByyyy_re   = re.compile(r'(?:^|[^\d])'  + any_dres + brres     + any_mres + brres          + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
YYyymmdd_re     = re.compile(r'(?:^|[^\d])'  + yres                 + mres                      + dres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
yyyymmdd_re     = re.compile(r'(?:^|[^\d])'  + yres                 + mres                      + dres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
mmZZyyyy_re     = re.compile(r'(?:^|[^\d])'  + mres                 + r'00'                     + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
ZZZZyyyy_re     = re.compile(r'(?:^|[^\d])'  + r'00'                + r'00'                     + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
yyyymmZZ_re     = re.compile(r'(?:^|[^\d])'  + yres                 + mres                      + r'00'                                 + r'(?:[^\d]|$)',       re.IGNORECASE)
yyyyZZZZ_re     = re.compile(r'(?:^|[^\d])'  + yres                 + r'00'                     + r'00'                                 + r'(?:[^\d]|$)',       re.IGNORECASE)
mmyyyy_re       = re.compile(r'(?:^|[^\d])'                         + mres                      + yres                                  + r'(?:[^\d]|$)',       re.IGNORECASE)
yyyymm_re       = re.compile(r'(?:^|[^\d])'  + yres                 + mres                                                              + r'(?:[^\d]|$)',       re.IGNORECASE)
yyyy_re         = re.compile(r'(?:^|[^\d])'  + yres                                                                                     + r'(?:[^\d]|$)',       re.IGNORECASE)
d_mnm_re        = re.compile(r'(?:^|[^\d])'  + any_dres             + r'[\/\-\s]*'              + mn_res                                + r'(?:[^\da-z]|$)',    re.IGNORECASE)
mnmS_d_re       = re.compile(r'(?:^|[^a-z])'                                                    + mn_res    + r'[\/\-\s\.]*'+ any_dres  + r'(?:[^\d]|$)',       re.IGNORECASE)

about_re        = re.compile(r'(?<![a-z])(prob(ably)?|maybe|abo?u?t?\.?|appro?x?|aproximadamente?|around|est(im(ated?)?|\.)?|c(erca|\.)?|ca\.?|cir)(?![a-z])',  re.IGNORECASE)
after_re        = re.compile(r'(?<![a-z])(afte?r?\.?|since)(?![a-z])',                                  re.IGNORECASE)
before_re       = re.compile(r'(?<![a-z])(((befo?r?e?|bfo?r)\.?)|by(?!\s+census)|as\s+of)(?![a-z])',    re.IGNORECASE)

alive_re        = re.compile(r'(^No?$|(?<![a-z])not\s+(deceased?|dead|daed|died|deid|dec)(?![a-z]))',   re.IGNORECASE)
dead_re         = re.compile(r'''
                                (
                                    ^\(?dec\)?$                             # for some reason this won't go in the big list below, so we just look for it specifically here
                                  | ^Y(es)?$
                                  | (?<![a-z])                              # all these preceded by a non-alpha character that's not included in a sub()
                                    (
                                            Find\s+A\s+Grave\s+Memorial(\s*\#\s*\d+)?
                                        |   d\.(\s*y)?
                                        |   deceas?e?d?
                                        |   \(dead\)
                                        |   dead
                                        |   daed
                                        |   died
                                        |   deid
                                        |   death
                                        |   stillborn
                                        |   stlbrn
                                        |   crea?m[ea]t(ed?|ion)
                                        |   (
                                                WW
                                              | world\s+war
                                            )
                                            (
                                                            \s*II?
                                                        |   \s+one
                                                        |   \s+two
                                            )

                                        |   (
                                                church(yard)?\s+
                                              | rural\s+
                                            )?
                                            c[ei]m[ae]t[ae]ry
                                        |   church(yard)?
                                        |   bur(i[ae]l|ying)\s+ground
                                        |   bur\.?
                                        |   \(child\)
                                        |   child
                                        |   \(yo?u?ng\)
                                        |   yo?u?ng
                                        |   \(old\)
                                        |   old
                                        |   \(infan(t|cy)\)
                                        |   infan(t|cy)
                                        |   \(at\s+birth\)
                                        |   at\s+birth
                                    )
                                    (?![a-z])                               # all these followed by a non-alpha character
                                )''', re.IGNORECASE | re.VERBOSE)


date_cache      = {}            # to speed up programs, we'll remember all the a_date()'s we've calculated. keyed by the original string, valued by a_date() (Note the user can futz with the a_date() and mess himself up if he doesn't know we have it cached.)

#
#
#   TODO
#
#       Aside from doing all the dates in a wordlist file (below):
#
#           python(3) -c "import sys;sys.path.append('python-gedcom');import gedcom as g;g.Gedcom('file_name.ged').print_dates()" >parsed_dates.txt
#
#       1847/9
#       1847/49
#       1847 / 1849
#       from a_date to a_date
#       a_date (and|or|to|[/\-]) a_date
#       (EITHER)? a_date OR a_date
#       BET(WEEN)? a_date (AND|\&) a_date
#       19050830                                ambiguous ordering - find likeliest - same for (mm/dd/yyyy|dd/mm/yyyy) (mmddyyyy|ddmmyyyy)
#       -1987                                   before 1987 or if death, then just the year
#       1987-                                   after  1987 or if birth, then just the year
#       1987 -                                  after  1987 or if birth, then just the year
#       1027                                    mmyy                no - or disambiguate
#       1204                                    mmyy                no - or disambiguate
#       12 Sep 1820 (1822?)
#       to 1780                                 1780                is wrong - should be "before 1780"
#       1820 or before                          before 1820         ????
#       January or February 1739/1740           February 1739
#       Dec 1900                                                    deceased 1900 or December 1900 ????
#       16 MAR 1731–2
#       10Feb1718-19
#       1734/35/36                              1734
#       12-1790                                 1790                is wrong
#       1569-01-11/+1570-01-10                  1569                is wrong
#       1733-05-14                              1733                is wrong
#       1993 July                               1993                is wrong
#       AFT 5-MAY-1783                          after 1783          is wrong
#       25 December 16911691                    25 December         is wrong (fix the duped year)
#       2 December or Jan. 1639/40              January 1639        2 December 1639 or January 1640 ????
#       Bet. 04 Jul–18 Sep 1731               18 September 1731
#       Betw 17 Sept 1683 & 29 June 1685        17 September 1683
#       1661/1754                                                   for MK6D-ZXM
#       17 Jun 1790 age 38                                          age could be cross-checked
#       1May1674 (age 71)                                           age could be cross-checked
#       1741–9 April 1743                     9 April 1743        ????
#       KZX7-4LP    1823 (ae 28 - 1851)         1823
#       L7RS-FSD    19Feb1680-81 or Dec1680     19 February 1680
#       About:1860-00-00                        about 1860          for example
#
#

class   a_date(object) :

    def __init__(me, y = None, m = None, d = None, about = False, before = False, after = False) :
        me.year     = None if not y else int(y)             # None or the year 1..20xx
        me.month    = None if not m else int(m)             # None or the month 1..12
        me.day      = None if not d else int(d)             # None or the day of month 1..31
        me.about    = (about  and True) or False            # whether the date string had "about"       or equivalent
        me.before   = (before and True) or False            # whether the date string had "before"      or equivalent
        me.after    = (after  and True) or False            # whether the date string had "after"       or equivalent


    def if_valid(me) :
        """ Return ourself if we're valid. Otherwise, return None. """
        if  me.month and me.day :
            d       = me.day
            if  ((me.year or 0) & 1) and (me.month == 2) and (d == 29) :
                d  += 1                                     # odd years aren't leap years (we should probably go ahead and do a real leap year check, but, really, dates get weird back some years ago, what with the calender changes and all)
            if  (not (1 <= me.month <= 12)) or (not (1 <= d <= days_in_months[me.month])) :
                return None
            pass
        return me


    @staticmethod
    def parse(d) :
        """ Return None or a_date() for the given date string. """
        if  d in date_cache :
            return date_cache[d]
        od      = d

        date    = None
        d       = best_ascii((d or '').strip().lower())         # best_ascii() to match up with the month names, which have already been best_ascii()'d
        if  d   :
            abt     = about_re.search(d)
            if  abt :
                d   = about_re.sub('', d)
            aft     = after_re.search(d)
            if  aft :
                d   = after_re.sub('', d)
            bef     = before_re.search(d)
            if  bef :
                d   = before_re.sub('', d)
            d       = d.strip()
            if  not date :
                g       = d_mnm_y_re.search(d)
                if  g   :
                    bm  = best_month(g.group(2))
                    if  bm > 0  :
                        date    = a_date(g.group(3), bm, g.group(1),         about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            if  not date :
                g       = mnm_d_y_re.search(d)
                if  g   :
                    bm  = best_month(g.group(1))
                    if  bm > 0  :
                        date    = a_date(g.group(3), bm, g.group(2),         about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            if  not date :
                g       = mnm_d_re.search(d)
                if  g   :
                    bm  = best_month(g.group(1))
                    if  bm > 0  :
                        date    = a_date(m = bm, d = g.group(2),            about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            if  not date :
                g       = mnm_y_re.search(d)
                if  g   :
                    bm  = best_month(g.group(1))
                    if  bm > 0  :
                        date    = a_date(g.group(2), bm,                     about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            for rx in [ mmsddsyyyy_re, mmDddDyyyy_re, mmBddByyyy_re, ] :
                if  not date    :
                    g           = rx.search(d)
                    if  g       :
                        date    = a_date(g.group(3), g.group(1), g.group(2), about = abt, before = bef, after = aft).if_valid()
                        break
                    pass
                pass
            for rx in [ ddsmmsyyyy_re, ddDmmDyyyy_re, ddBmmByyyy_re, ] :
                if  not date    :
                    g           = rx.search(d)
                    if  g       :
                        date    = a_date(g.group(3), g.group(2), g.group(1), about = abt, before = bef, after = aft).if_valid()
                        break
                    pass
                pass
            if  not date    :
                g           = mmddYYyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(3), g.group(1), g.group(2), about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = ddmmYYyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(3), g.group(1), g.group(2), about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = YYyymmdd_re.search(d)
                if  g       :
                    date    = a_date(g.group(1), g.group(2), g.group(3),     about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = mmddyyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(3), g.group(1), g.group(2), about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = ddmmyyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(3), g.group(1), g.group(2), about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = yyyymmdd_re.search(d)
                if  g       :
                    date    = a_date(g.group(1), g.group(2), g.group(3),     about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = mmZZyyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(2), g.group(1),                 about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = ZZZZyyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(1),                             about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = yyyymmZZ_re.search(d)
                if  g       :
                    date    = a_date(g.group(1), g.group(2),                 about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = yyyyZZZZ_re.search(d)
                if  g       :
                    date    = a_date(g.group(1),                             about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = mmyyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(2), g.group(1),                 about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = yyyymm_re.search(d)
                if  g       :
                    date    = a_date(g.group(1), g.group(2),                 about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date    :
                g           = yyyy_re.search(d)
                if  g       :
                    date    = a_date(g.group(1),                             about = abt, before = bef, after = aft).if_valid()
                pass
            if  not date :
                g       = d_mnm_re.search(d)
                if  g   :
                    bm  = best_month(g.group(2))
                    if  bm > 0  :
                        date    = a_date(m = bm, d = g.group(1),             about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            if  not date :
                g       = mnmS_d_re.search(d)
                if  g   :
                    bm  = best_month(g.group(1))
                    if  bm > 0  :
                        date    = a_date(m = bm, d = g.group(2),             about = abt, before = bef, after = aft).if_valid()
                    pass
                pass
            if  False       :
                if  not date :
                    print("@@@@ >>>> %s" % od)
                else        :
                    print("@@@@ ---- %s ---- %s" % ( od, str(date), ))
                pass
            pass

        date_cache[od]      = date

        return date


    @staticmethod
    def parse_death_date(d) :
        """ Return None or a_date() for the given date string. """
        od          = d
        if  d not  in date_cache :
            dd      = d
            d       = (d or '').strip().lower()
            if  d and (not alive_re.search(d)) and dead_re.search(d) :
                d   = dead_re.sub('', d).strip()
                if  len(d) < 24     :
                    dd              = d
                pass
            # print("@@@@ death dd:[" + dd + "] ", end = '')
            date                    = a_date.parse(dd)
            date_cache[od]          = date                  # also, put it under the original string in case it's different from dd
            if  not date            :
                if  dd != od        :
                    date            = a_date()              # give them an empty date indicating the guy is dead, even if we don't know when
                    date_cache[od]  = date                  # we really know what the cache item should be
                pass
            pass
        return date_cache[od]


    def to_string(me) :
        ys          = "" if me.year  is None else "%04d" % me.year
        if  1 <= (me.month or 0) <= 12 :
            ms      = string.capwords(month_names[0][me.month - 1]) + " "
        else        :
            ms      = ""
        ds          = "" if me.day   is None else "%u " % me.day
        abt         = (me.about  and "about " ) or ""
        bef         = (me.before and "before ") or ""
        aft         = (me.after  and "after " ) or ""
        return (abt + bef + aft + ds + ms + ys).strip()
    __str__         = to_string

    #   a_date


class Gedcom(object):
    """Parses and manipulates GEDCOM 5.5 format data

    For documentation of the GEDCOM 5.5 format, see:
    http://homepages.rootsweb.ancestry.com/~pmcbride/gedcom/55gctoc.htm

    This parser reads and parses a GEDCOM file.
    Elements may be accessed via:
      - a list (all elements, default order is same as in file)
      - a dict (only elements with pointers, which are the keys)

    Python3 args (ignored by Python2) passed to open(). (all added by github:rltest):

    encoding - set the file encoding. Default: None.

    errors   - behavior for handling (unicode decode) errors. (added by github:mwhite)

    newline  - Default: CR LF

    opener   - Default: None


    """

    def __init__(self, filepath,
                       encoding=None,
                       errors=None,
                       newline=None,
                       opener=None,
                ):
        """ Initialize a GEDCOM data object. You must supply a Gedcom file."""
        self.__element_list = []
        self.__element_dict = {}
        self.__element_top  = Element(-1, "", "TOP", "")
        self.__parse(filepath, errors=errors)
        self.encode         = ''

    def element_list(self):
        """ Return a list of all the elements in the Gedcom file.

        By default elements are in the same order as they appeared in the file.
        """
        return self.__element_list

    def element_dict(self):
        """Return a dictionary of elements from the Gedcom file.

        Only elements identified by a pointer are listed in the dictionary.
        The keys for the dictionary are the pointers.
        """
        return self.__element_dict

    # Private methods

    def __parse(self, filepath,
                      encoding=None,
                      errors=None,
                      newline=None,
                      opener=None,
               ):
        """Open and parse file path as GEDCOM 5.5 formatted data."""
        if  sys.version_info[0] >= 3 :
            gedcom_file = open(filepath,
                               mode='rU',
                               encoding=encoding,
                               errors = errors,
                               newline=None,        # github:rltest: \r\n is part of the gedcom 5.5 spec. bar: But be liberal in what we accept.
                               opener=opener,
                              )
            pass
        else:
            gedcom_file = open(filepath, 'rU')

        utf_hdr     = gedcom_file.read(1)
        if  utf_hdr == '\ufeff':                    # python3
            self.encode = 'utf8'                    # maybe we should do something with this, but if we're defaulting to utf8, it's hard to say what
        else:
            utf_hdr    += gedcom_file.read(2)
            if  utf_hdr == '\xef\xbb\xbf':          # python2
                self.encode = 'utf8'
            else:
                gedcom_file.seek(0)                 # normal file
            pass

        line_num = 1
        last_elem = self.__element_top
        for line in gedcom_file:
            last_elem = self.__parse_line(line_num, line, last_elem)
            line_num += 1
        gedcom_file.close()

    def __parse_line(self, line_num, line, last_elem):
        """Parse a line from a GEDCOM 5.5 formatted document.

        Each line should have the following (bracketed items optional):
        level + ' ' + [pointer + ' ' +] tag + [' ' + line_value]
        """
        g   = ged_line_re.match(line)
        if  g:
            line_parts = g.groups()
        elif not line.strip():
            return last_elem                    # allow blank lines
        else:
            errmsg = ("Line %d of document violates GEDCOM format" % line_num +
                      "\nSee: http://homepages.rootsweb.ancestry.com/" +
                      "~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(errmsg)

        level   = int(line_parts[0])
        pointer = line_parts[1].rstrip(' ')
        tag     = line_parts[2]
        value   = line_parts[3][1:]         # not .lstrip(' ') so CONC elements can have leading spaces so as not to need trailing spaces   - from github:mtdcr
        crlf    = line_parts[4]             # github:mtdcr

        # Check level: should never be more than one higher than previous line.
        if level > last_elem.level() + 1:
            errmsg = ("Line %d of document violates GEDCOM format" % line_num +
                      "\nLines must be no more than one level higher than " +
                      "previous line.\nSee: http://homepages.rootsweb." +
                      "ancestry.com/~pmcbride/gedcom/55gctoc.htm")
            raise SyntaxError(errmsg)

        # Create element. Store in list and dict, create children and parents.
        element = Element(level, pointer, tag, value, crlf)
        self.__element_list.append(element)
        if pointer != '':
            self.__element_dict[pointer] = element

        # Start with last element as parent, back up if necessary.
        parent_elem = last_elem
        while parent_elem.level() > level - 1:
            parent_elem = parent_elem.parent()
        # Add child to parent & parent to child.
        parent_elem.add_child(element)
        element.add_parent(parent_elem)
        return element

    # Methods for analyzing individuals and relationships between individuals

    def marriage(self, individual1, individual2):   # from github:albarralnunez
        """ Get de date and place of a marraige if this exists """
        if not individual1.is_individual() and not individual2.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        fams_families1 = set(self.families(individual1, "FAMS"))
        fams_families2 = set(self.families(individual2, "FAMS"))
        family = list(fams_families1.intersection(fams_families2))
        if family:
            # print family
            # print family[0].children()
            for famdata in family[0].children():
                if famdata.tag() == "MARR" or famdata.tag() == 'DIV':
                    for marrdata in famdata.children():
                        date = ''
                        place = ''
                        if marrdata.tag() == "DATE":
                            date = marrdata.value().strip()
                        if marrdata.tag() == "PLAC":
                            place = marrdata.value().strip()
                        return date, place
        return None, None

    def marriage_date(self, individual1, individual2):
        """ Return a_date() or None for the person's marriage date. """
        return a_date.parse(self.marriage(individual1, individual2)[0])

    def marriages(self, individual):
        """ Return list of marriage tuples (date, place) for an individual. """
        marriages = []
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        # Get and analyze families where individual is spouse.
        fams_families = self.families(individual, "FAMS")
        for family in fams_families:
            for famdata in family.children():
                if famdata.tag() == "MARR":
                    for marrdata in famdata.children():
                        date = ''
                        place = ''
                        if marrdata.tag() == "DATE":
                            date = marrdata.value().strip()
                        if marrdata.tag() == "PLAC":
                            place = marrdata.value().strip()
                        marriages.append((date, place))
        return marriages

    def marriage_dates(self, individual):
        """ Return a_date() or None's for the person's marriage dates. """
        return [ a_date.parse(dp[0]) for dp in self.marriages(individual) ]

    def marriage_years(self, individual):
        """ Return list of marriage years (as int) for an individual. """
        marriages   = self.marriages(individual)
        dates       = []
        for m in marriages :
            d       = a_date.parse(m[0])
            if  d and (d.year != None) :
                dates.append(d.year)
            pass
        return dates

    def marriage_year_match(self, individual, year):
        """ Check if one of the marriage years of an individual matches
        the supplied year.  Year is an integer. """
        years = self.marriage_years(individual)
        return year in years

    def marriage_range_match(self, individual, year1, year2):
        """ Check if one of the marriage year of an individual is in a
        given range.  Years are integers.
        """
        years = self.marriage_years(individual)
        for year in years:
            if year >= year1 and year <= year2:
                return True
        return False

    def families(self, individual, family_type="FAMS"):
        """ Return family elements listed for an individual.

        family_type can be FAMS (families where the individual is a spouse) or
        FAMC (families where the individual is a child). If a value is not
        provided, FAMS is default value.
        """
        if not individual.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        families = []
        for child in individual.children():
            is_fams = (child.tag() == family_type and
                       child.value() in self.__element_dict and
                       self.__element_dict[child.value()].is_family())
            if is_fams:
                families.append(self.__element_dict[child.value()])
        return families

    def get_ancestors(self, indi, anc_type="ALL"):
        """ Return elements corresponding to ancestors of an individual

        Optional anc_type. Default "ALL" returns all ancestors, "NAT" can be
        used to specify only natural (genetic) ancestors.
        """
        if not indi.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = self.get_parents(indi, anc_type)
        ancestors = parents
        for parent in parents:
            ancestors = ancestors + self.get_ancestors(parent)
        return ancestors

    def get_parents(self, indi, parent_type="ALL"):
        """ Return elements corresponding to parents of an individual

        Optional parent_type. Default "ALL" returns all parents. "NAT" can be
        used to specify only natural (genetic) parents.
        """
        if not indi.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag.")
        parents = []
        famc_families = self.families(indi, "FAMC")
        for family in famc_families:
            if parent_type == "NAT":
                for famrec in family.children():
                    if famrec.tag() == "CHIL" and famrec.value() == indi.pointer():
                        for chilrec in famrec.children():
                            if chilrec.value() == "Natural":
                                if chilrec.tag()   in [ "_MREL", "MREL", ]:             # github:d2po swapped M/F - checked against gramps exportgedcom.py code. bar: added non-underscore tags
                                    parents = (parents +
                                               self.get_family_members(family, "WIFE"))
                                elif chilrec.tag() in [ "_FREL", "FREL", ]:             # github:d2po ditto
                                    parents = (parents +
                                               self.get_family_members(family, "HUSB"))
            else:
                parents = parents + self.get_family_members(family, "PARENTS")
        return parents

    def get_children(self, indi):
        """ Return array of children of this person. """
        children        = []
        for fam in self.families(indi):
            children   += self.get_family_members(fam, mem_type = "CHIL")
        return children

    def find_path_to_anc(self, desc, anc, path=None, anc_type="ALL"):
        """ Return path from descendant to ancestor. """
        if not desc.is_individual() and anc.is_individual():
            raise ValueError("Operation only valid for elements with IND tag.")
        if not path:
            path = [desc]
        if path[-1].pointer() == anc.pointer():
            return path
        else:
            parents = self.get_parents(desc, anc_type)
            for par in parents:
                potential_path = self.find_path_to_anc(par, anc, path + [par])
                if potential_path:
                    return potential_path
        return None

    def get_family_members(self, family, mem_type="ALL"):
        """Return array of family members: individual, spouse, and children.

        Optional argument mem_type can be used to return specific subsets.
        "ALL": Default, return all members of the family
        "PARENTS": Return individuals with "HUSB" and "WIFE" tags (parents)
        "HUSB": Return individuals with "HUSB" tags (father)
        "WIFE": Return individuals with "WIFE" tags (mother)
        "CHIL": Return individuals with "CHIL" tags (children)
        """
        if not family.is_family():
            raise ValueError("Operation only valid for elements with FAM tag.")
        family_members = [ ]
        for elem in family.children():
            # Default is ALL
            is_family = (elem.tag() == "HUSB" or
                         elem.tag() == "WIFE" or
                         elem.tag() == "CHIL")
            if mem_type == "PARENTS":
                is_family = (elem.tag() == "HUSB" or
                             elem.tag() == "WIFE")
            elif mem_type == "HUSB":
                is_family = (elem.tag() == "HUSB")
            elif mem_type == "WIFE":
                is_family = (elem.tag() == "WIFE")
            elif mem_type == "CHIL":
                is_family = (elem.tag() == "CHIL")
            if is_family and elem.value() in self.__element_dict:
                family_members.append(self.__element_dict[elem.value()])
        return family_members

    # Other methods

    def print_gedcom(self, file=None, flush=False):     # file+flush are p2 compat version of github:rltest changes
        """Write GEDCOM data to stdout."""
        file    = file or sys.stdout
        for element in self.element_list():
            file.write(str(element))
            if  flush:
                file.flush()                            # this can keep tail up to date, eh?
            pass
        pass

    def print_dates(self):
        """
            Help with testing by printing all the dates we know for ourself.

            python(3) -c "import sys;sys.path.append('python-gedcom');import gedcom as g;g.Gedcom('GEDcom_file.ged').print_dates()"

        """
        for element in self.element_list():
            element.print_dates()
        pass



class GedcomParseError(Exception):
    """ Exception raised when a Gedcom parsing error occurs
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class Element(object):
    """ Gedcom element

    Each line in a Gedcom file is an element with the format

    level [pointer] tag [value]

    where level and tag are required, and pointer and value are
    optional.  Elements are arranged hierarchically according to their
    level, and elements with a level of zero are at the top level.
    Elements with a level greater than zero are children of their
    parent.

    A pointer has the format @pname@, where pname is any sequence of
    characters and numbers.  The pointer identifies the object being
    pointed to, so that any pointer included as the value of any
    element points back to the original object.  For example, an
    element may have a FAMS tag whose value is @F1@, meaning that this
    element points to the family record in which the associated person
    is a spouse.  Likewise, an element with a tag of FAMC has a value
    that points to a family record in which the associated person is a
    child.

    See a Gedcom file for examples of tags and their values.

    """

    def __init__(self, level, pointer, tag, value, crlf=None):
        """ Initialize an element.

        You must include a level, pointer, tag, and value. Normally
        initialized by the Gedcom parser, not by a user.
        """
        # basic element info
        self.__level = level
        self.__pointer = pointer
        self.__tag = tag
        self.__value = value
        self.__crlf = crlf or "\n"
        # structuring
        self.__children = []
        self.__parent = None

    def level(self):
        """ Return the level of this element """
        return self.__level

    def pointer(self):
        """ Return the pointer of this element """
        return self.__pointer

    def tag(self):
        """ Return the tag of this element """
        return self.__tag

    def value(self):
        """ Return the value of this element """
        return self.__value

    def children(self):
        """ Return the child elements of this element """
        return self.__children

    def parent(self):
        """ Return the parent element of this element """
        return self.__parent

    def add_child(self,element):
        """ Add a child element to this element """
        self.children().append(element)

    def add_parent(self,element):
        """ Add a parent element to this element """
        self.__parent = element

    def is_individual(self):
        """ Check if this element is an individual """
        return self.tag() == "INDI"

    def is_family(self):
        """ Check if this element is a family """
        return self.tag() == "FAM"

    def is_file(self):                  # github:mtdcr
        """ Check if this element is a file """
        return self.tag() == "FILE"

    def is_object(self):                # github:mtdcr
        """ Check if this element is an object """
        return self.tag() == "OBJE"


    # criteria matching

    def criteria_match(self,criteria):
        """ Check in this element matches all of the given criteria.
        The criteria is a colon-separated list, where each item in the

        list has the form [name]=[value]. The following criteria are supported:

        surname=[name]
             Match a person with [name] in any part of the surname.
        name=[name]
             Match a person with [name] in any part of the given name.
        birth=[year]
             Match a person whose birth year is a four-digit [year].
        birthrange=[year1-year2]
             Match a person whose birth year is in the range of years from
             [year1] to [year2], including both [year1] and [year2].
        death=[year]
        deathrange=[year1-year2]
        """

        # error checking on the criteria
        try:
            for crit in criteria.split(':'):
                key,value = crit.split('=')
        except:
            return False
        match = True
        for crit in criteria.split(':'):
            key,value = crit.split('=')
            if key == "surname" and not self.surname_match(value):
                match = False
            elif key == "name" and not self.given_match(value):
                match = False
            elif key == "birth":
                try:
                    year = int(value)
                    if not self.birth_year_match(year):
                        match = False
                except:
                    match = False
            elif key == "birthrange":
                try:
                    year1,year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.birth_range_match(year1,year2):
                        match = False
                except:
                    match = False
            elif key == "death":
                try:
                    year = int(value)
                    if not self.death_year_match(year):
                        match = False
                except:
                    match = False
            elif key == "deathrange":
                try:
                    year1,year2 = value.split('-')
                    year1 = int(year1)
                    year2 = int(year2)
                    if not self.death_range_match(year1,year2):
                        match = False
                except:
                    match = False

        return match

    def surname_match(self,name):
        """ Match a string with the surname of an individual """
        (first,last) = self.name()
        return last.find(name) >= 0

    def given_match(self,name):
        """ Match a string with the given names of an individual """
        (first,last) = self.name()
        return first.find(name) >= 0

    def birth_year_match(self,year):
        """ Match the birth year of an individual.  Year is an integer. """
        return self.birth_year() == year

    def birth_range_match(self,year1,year2):
        """ Check if the birth year of an individual is in a given range.
        Years are integers.
        """
        year = self.birth_year()
        if year >= year1 and year <= year2:
            return True
        return False

    def death_year_match(self,year):
        """ Match the death year of an individual.  Year is an integer. """
        return self.death_year() == year

    def death_range_match(self,year1,year2):
        """ Check if the death year of an individual is in a given range.
        Years are integers.
        """
        year = self.death_year()
        if year >= year1 and year <= year2:
            return True
        return False

    def name(self):
        """ Return a person's names as a tuple: (first,last) """
        first = ""
        last = ""
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "NAME":
                    # some older Gedcom files don't use child tags but instead
                    # place the name in the value of the NAME tag
                    for c in e.children():
                        if c.tag() == "GIVN":
                            first = c.value().strip()
                        if c.tag() == "SURN":
                            last = c.value().strip()
                    if  (not first) and (not last):
                        if e.value().strip() != "":
                            name = e.value().split('/')
                            if len(name) > 0:
                                first = name[0].strip()
                                if len(name) > 1:
                                    last = name[1].strip()
        return (first,last)

    def gender(self):
        """ Return the gender of a person in string format """
        gender = ""
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "SEX":
                    gender = e.value().strip()
                    break
        return gender

    def private(self):
        """ Return if the person is marked private in boolean format """
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "PRIV":
                    if  e.value().strip() == 'Y':
                        return True
        return False

    def birth(self):
        """ Return the birth tuple of a person as (date,place,source) """
        date = ""
        place = ""
        source = ()
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "BIRT":
                    for c in e.children():
                        if c.tag() == "DATE":
                            date = c.value()
                        if c.tag() == "PLAC":
                            place = c.value()
                        if c.tag() == "SOUR":
                            source = source + (c.value(),)
        return (date,place,source)          # note: the file could make this return value a mish-mash

    def birth_date(self):
        """ Return a_date() or None for the person's birth date. """
        return a_date.parse(self.birth()[0])

    def birth_year(self):
        """ Return the birth year of a person in integer format """
        date = self.birth_date()
        if  date and (date.year != None) :
            return date.year
        return -1

    def death(self):
        """ Return the death tuple of a person as (date,place,source) """
        date = ""
        place = ""
        source = ()
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "DEAT":
                    for c in e.children():
                        if c.tag() == "DATE":
                            date = c.value()
                        if c.tag() == "PLAC":
                            place = c.value()
                        if c.tag() == "SOUR":
                            source = source + (c.value(),)
        return (date,place,source)

    def death_date(self):
        """ Return a_date() or None for the person's death date. """
        return a_date.parse_death_date(self.death()[0])

    def death_year(self):
        """ Return the death year of a person in integer format """
        date = self.death_date()
        if  date and (date.year != None) :
            return date.year
        return -1

    def burial(self):
        """ Return the burial tuple of a person as (date,place,source) """
        date = ""
        place = ""
        source = ()
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "BURI":
                    for c in e.children():
                        if c.tag() == "DATE":
                            date = c.value()
                        if c.tag() == "PLAC":
                            place = c.value()
                        if c.tag() == "SOUR":
                            source = source + (c.value(),)
        return (date,place,source)

    def burial_date(self):
        """ Return a_date() or None for the person's burial date. """
        return a_date.parse_death_date(self.burial()[0])

    def census(self):
        """ Return list of census tuples (date, place) for an individual. """
        census = []
        if not self.is_individual():
            raise ValueError("Operation only valid for elements with INDI tag")
        for pdata in self.children():
            if pdata.tag() == "CENS":
                date = ''
                place = ''
                source = ''
                for indivdata in pdata.children():
                    if indivdata.tag() == "DATE":
                        date = indivdata.value()
                    if indivdata.tag() == "PLAC":
                        place = indivdata.value()
                    if indivdata.tag() == "SOUR":
                        source = source + (indivdata.value(),)
                census.append((date, place, source))
        return census

    def census_dates(self):
        """ Return a_date() or None's for the person's census dates. """
        return [ a_date.parse(dps[0]) for dps in self.census() ]

    def last_updated(self):
        """ Return the last updated date of a person as date string """
        date = ""
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "CHAN":
                    for c in e.children():
                        if c.tag() == "DATE":
                            date    = c.value().strip()
        return date

    def last_updated_date(self):
        """ Return a_date() or None for the person's birth date. """
        return a_date.parse(self.last_updated())

    def occupation(self):
        """ Return the occupation of a person as a string. """
        occupation = ""
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "OCCU":
                    occupation = e.value().strip()
        return occupation

    def deceased(self):
        """ Check if a person is deceased """
        if  self.is_individual():
            for e in self.children():
                if e.tag() == "DEAT":
                    return True
        return False


    def get_values_list(self, tag):
        """
            Return an array of values for the given tag, assuming there may be zero or more children of 'self' with the tag.

            Return [] if the tag is not found.

        """
        return list(e.value() for e in self.children() if e.tag() == tag)


    def get_string_value(self, tag):
        """
            Return the string value for the first tag found.

            Return "" if we are not an individual or the tag is not found.

        """
        if  self.is_individual():
            for e in self.children():
                if  e.tag() == tag:
                    return e.value()
        return ""


    def family_search_id(self):
        """ Return the FamilySearch.org ID string of this person or "", if it's not given. """
        return(self.get_string_value("_FSFTID"))

    def afn(self):
        """ Return the Ancestral File Number string of this person or "", if it's not given. """
        return(self.get_string_value("AFN"))

    def mh_rin(self):
        """ Return the HyHeritage RIN string of this person or "", if it's not given. """
        return(self.get_string_value("RIN"))

    def uid(self):
        """ Return the _UID string of this person or "", if it's not given. """
        return(self.get_string_value("_UID"))

    def user_ref_num(self):
        """ Return the User Reference Number / REFN string of this person or "", if it's not given. """
        return(self.get_string_value("REFN"))

    def get_individual(self):
        """ Return this element and all of its sub-elements """
        result = str(self)
        for e in self.children():
            result += e.get_individual()
        return result

    def __str__(self):
        """ Format this element as its original string """
        result = str(self.level())
        if self.pointer() != "":
            result += ' '  + self.pointer()
        result     += ' '  + self.tag()
        if self.value()   != "":
            result += ' '  + self.value()
        result     += self.__crlf
        return result

    def _print_dates(self, ident = None, parse_rtn = None):
        """ Help with testing by printing all the dates we know for ourself. """
        ident   = ident or self.family_search_id() or self.afn() or self.mh_rin() or self.uid() or self.user_ref_num() or self.pointer()
        for e in self.children():
            if  e.tag() == "DATE" :
                parse_rtn   = parse_rtn or a_date.parse
                print("%s %-*s %-32s %s" % ( " " * e.level(), 18 - e.level(), ident[:12], e.value(), str(parse_rtn(e.value())), ))
            e._print_dates(ident, parse_rtn or ((e.tag() in [ 'DEAT', 'BURI', ]) and a_date.parse_death_date) or None)
        pass
    def print_dates(self):
        """ Help with testing by printing all the dates we know for ourself. """
        if  not self.level() :
            self._print_dates()
        pass


if  False   :
    parse   = a_date.parse_death_date
    parse   = a_date.parse
    fd      = open('../../words/wiktionary/tv_word_counts.txt', 'r').read()
    wrds    = re.findall(r'(?m)^(\S+)', fd)
    for w in wrds :
        w   = "1 " + w + " 1900"
        d   = parse(w)
        if  d and d.month:
            print("%-24s %s    " % ( d, w, ), end = "")
            HELPP   = " "
            del(date_cache[w])
            d   = parse(w)
            HELPP   = ""
            print("")
        pass
    pass


if  __name__ == '__main__':
    import  os

    if  (len(sys.argv) != 2) or (not os.path.isfile(sys.argv[1])):
        sys.stderr.write("I take an input .ged file which I print my parsed version of.\n")
    else:
        Gedcom(sys.argv[1]).print_gedcom(flush = True)
    pass


__all__ = ["Gedcom", "Element", "GedcomParseError", ged_line_re, a_date, date_cache, ]


#
# eof
