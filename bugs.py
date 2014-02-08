#!/usr/bin/env python
# -*- coding: utf8 -*-

################################################################################
#
#   Copyright (c) 2013-2014, Alexander Todorov <atodorov@nospam.dif.io>
#
#   Bug handling utilities.
#
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
################################################################################

import re
from BeautifulSoup import BeautifulSoup
from datetime import datetime, timedelta

def extract_bug_numbers(alist):
    """
        Remove the text from "issue #123" and
        return numbers.

        @alist - list of strings
        @return - dict - { number : text context}
    """
    result = {}

    for context in alist:
        # skip well known failures
        known_found = False
        for known in ['UTF-', 'CVE-', 'ASCII-', 'ISO-', 'PEP-', 'GMT-', 'RDS-', 'SQS-', 'EMR-', 'ECMA-', 'SHA-', 'RFC-', 'DB-', 'IAM-']:
            if context.lower().find(known.lower()) > -1:
                known_found = True
                break

        if known_found:
            continue

        all_numbers = re.findall("\d+", context)
        for n in all_numbers:
            n = int(n)
            if n in result.keys():
                result[n] += " " + context
            else:
                result[n] = context

    return result


# NB: don't forget to add to
# extract_title_from_html() and
# models.BUG_TRACKER_CHOICES

BUG_TYPE_NONE = -2
BUG_TYPE_UNKNOWN = -1
BUG_TYPE_GITHUB = 0
BUG_TYPE_BUGZILLA = 1
BUG_TYPE_BITBUCKET = 2
BUG_TYPE_LAUNCHPAD = 3
BUG_TYPE_GOOGLE = 4
BUG_TYPE_TRAC = 5
BUG_TYPE_ROUNDUP = 6
BUG_TYPE_SOURCEFORGE = 7
BUG_TYPE_LIGHTHOUSE = 8
BUG_TYPE_RT = 9
BUG_TYPE_PLONE = 10
BUG_TYPE_RT_PERL_ORG = 11
BUG_TYPE_YUI_TRACKER = 12
BUG_TYPE_PIVOTAL_TRACKER = 13
BUG_TYPE_PEAR_PHP_NET = 14
BUG_TYPE_RUBYFORGE = 15
BUG_TYPE_REDMINE = 16
BUG_TYPE_LOGILAB_ORG = 17
BUG_TYPE_JIRA = 18
BUG_TYPE_WINCENT = 19

def extract_github(title, soup):
    title = soup.body.findAll('span', attrs={'class':"js-issue-title"})[0].text

    reported_on = soup.body.findAll('time', attrs={'class':"js-relative-date"})[0]['datetime'][:19]
    reported_on = datetime.strptime(reported_on, '%Y-%m-%dT%H:%M:%S')

    last_comment_on = None
    for time in soup.body.findAll('time', attrs={'class':'js-relative-date'}):
        last_comment_on = time['datetime'][:19]

    closed_on = None
    for div in soup.body.findAll('div'):
        if div.text.find('closed the') > -1:
            for time in div.findAll('time'):
                closed_on = time['datetime'][:19]
            break
        elif div.text.find('closed') > -1:
            closed_on = last_comment_on
            break
        elif div.text.find('Merge pull request') > -1:
            closed_on = last_comment_on
            break
        elif div.has_key('class') and div['class'] == "gh-header-status closed":
            # when viewing PRs as Anonymous user the comments that PR has been
            # merged do not appear so we rely on the status icon
            closed_on = last_comment_on
            break
        elif div.has_key('class') and div['class'] == "gh-header-status merged":
            closed_on = last_comment_on
            break



    if closed_on:
        closed_on = datetime.strptime(closed_on, '%Y-%m-%dT%H:%M:%S')

    return (title, reported_on, closed_on)


def extract_bugzilla(title, soup):
    title = re.findall('Bug \d+ &ndash;(.*)', title)[0]
    reported_on = None
    closed_on = None

    reported_found = False
    closed_found = False
    next_is_date = False

    for td in soup.body.findAll('td'):
        if (closed_on is not None) and (reported_on is not None):
            break

        # skip nested table cells
        if len(td.findAll('td')) > 0:
            continue

        if not reported_found:
            b = td.findAll('b')
            if (len(b) > 0) and (b[0].text.strip() == 'Reported'):
                reported_found = True
                next_is_date = True
                continue

        if next_is_date and (reported_on is None):
            reported_on = td.text
            reported_on = reported_on[:16]
            reported_on = datetime.strptime(reported_on, '%Y-%m-%d %H:%M')
            next_is_date = False
            continue


        if not closed_found:
            b = td.findAll('b')
            if (len(b) > 0) and (b[0].text.strip() == 'Modified'):
                closed_found = True
                next_is_date = True
                continue

        if next_is_date and (closed_on is None):
            closed_on = td.text
            closed_on = closed_on[:16]
            closed_on = datetime.strptime(closed_on, '%Y-%m-%d %H:%M')
            next_is_date = False
            continue


    return (title, reported_on, closed_on)

def extract_bitbucket(title, soup):
    title = soup.body.findAll('h1', attrs={'id':'issue-title'})[0].text

    reported_on = soup.body.findAll('div', attrs={'class':'issue-author'})[0].findAll('time')[0]['datetime']
    reported_on = reported_on[:19]
    reported_on = datetime.strptime(reported_on, '%Y-%m-%dT%H:%M:%S')

    closed_on = None
    for time in soup.body.findAll('ol', attrs={'id':'issues-comments'})[0].findAll('time'):
        closed_on = time['datetime']

    if closed_on: # could be None for NEW issues
        closed_on = closed_on[:19]
        closed_on = datetime.strptime(closed_on, '%Y-%m-%dT%H:%M:%S')


    return (title, reported_on, closed_on)


def extract_roundup(title, soup):
    try:
        title = re.findall('Issue \d+:(.*) - .* tracker', title)[0]
    except IndexError:
        title = re.findall('Issue \d+:(.*) - Repoze Bugs', title)[0]

    last_changed = None
    reported_on = None
    for td in soup.body.findAll('td', attrs={'class':'content'}):
        for p in td.findAll('p'):
            if p.text.find('Created on') > -1:
                reported_on = p.findAll('b')[0].text
                reported_on = datetime.strptime(reported_on, '%Y-%m-%d.%H:%M:%S')

                # to be used later
                last_changed = p.findAll('b')[2].text
                last_changed = datetime.strptime(last_changed, '%Y-%m-%d.%H:%M:%S')
                break

    closed_on = None
    for table in soup.body.findAll('table', attrs={'class':'form'}):
        for th in table.findAll('th'):
            if th.text.find('Status') > -1:
                status = th.parent.findAll('td')[1].text
                if status in ['resolved', 'deferred', 'testing', 'done-cbb']:
                    closed_on = last_changed
                    break

    return (title, reported_on, closed_on)

def extract_sourceforge(title, soup):
    try:
        title = re.findall('SourceForge.net: .* Detail: \d+ - (.*)', title)[0]
    except IndexError:
        # new SF design:
        title = soup.body.findAll('h2', attrs={'class':'dark title'})[0].text
        title = re.findall('#\d+ (.*)', title)[0]

    reported_on = None
    for div in soup.body.findAll('div', attrs={'class':'grid-4'}):
        if div.label and div.label.text.startswith('Created:') and div.span:
            reported_on = div.span['title'][:-7]
            reported_on = datetime.strptime(reported_on, '%a %b %d, %Y %H:%M')
            break

    closed_on = None
    if soup.body.findAll('span', attrs={'class':'closed'}):
        for div in soup.body.findAll('div', attrs={'class':'grid-4'}):
            if div.label and div.label.text.startswith('Updated:') and div.span:
                closed_on = div.span['title'][:-7]
                closed_on = datetime.strptime(closed_on, '%a %b %d, %Y %H:%M')
                break

    return (title, reported_on, closed_on)

def extract_trac(title, soup):
    title = re.findall('#\d+\s+\((.*)\)\s+', title)[0]

    reported_on = None
    div = soup.body.findAll('div', attrs={'class':'date'})[0]
    if div.p.text.find('Opened') > -1:
        reported_on = div.p.a['title']
        if reported_on.find('See timeline at') > -1: # Django Trac
            reported_on = reported_on.replace('See timeline at', '').strip()
            reported_on = datetime.strptime(reported_on, '%m/%d/%y %H:%M:%S')
        else:
            reported_on = reported_on[:19]
            reported_on = datetime.strptime(reported_on, '%Y-%m-%dT%H:%M:%S')

    closed_on = None
    for div in soup.body.findAll('div', attrs={'class':'change'}):
        for ul in div.findAll('ul', attrs={'class':'changes'}):
            for li in ul.findAll('li'):
                if re.findall('.*Status.*changed from.*to.*closed.*', li.text):
                    for a in div.h3.findAll('a', attrs={'class':'timeline'}):
                        closed_on = a['title']
                        if closed_on.find('See timeline at') > -1: # Django Trac
                            closed_on = closed_on.replace('See timeline at', '').strip()
                            closed_on = datetime.strptime(closed_on, '%m/%d/%y %H:%M:%S')
                        else:
                            closed_on = closed_on[:19]
                            closed_on = datetime.strptime(closed_on, '%Y-%m-%dT%H:%M:%S')

    return (title, reported_on, closed_on)

def extract_google(title, soup):
    title = soup.body.findAll('span', attrs={'class':"h3"})[0].text
    for div in soup.body.findAll('div', attrs={'class':'author'}):
        for span in div.findAll('span', attrs={'class' : 'date'}):
            reported_on = span['title']
            reported_on = datetime.strptime(reported_on, '%a %b %d %H:%M:%S %Y')
            break

    closed_on = None

    for tr in soup.body.findAll('div', attrs={'id':'meta-float'})[0].findAll('tr'):
        # issue is closed
        for th in tr.findAll('th'):
            if th.text.find('Closed:') > -1:
                # so take the date of the last comment
                for div in soup.body.findAll('div', attrs={'class':'cursor_off vt issuecomment'}):
                    for span in div.findAll('span', attrs={'class':'date'}):
                        closed_on = span['title']
                break

    if closed_on: # could be None
        closed_on = datetime.strptime(closed_on, '%a %b %d %H:%M:%S %Y')

    return (title, reported_on, closed_on)

def extract_lighthouse(title, soup):
    title = soup.body.findAll('h2')[0].text

    reported_on = None
    for div in soup.body.findAll('div', attrs={'id':'page-top'}):
        for p in div.findAll('p', attrs={'class':'date'}):
            if (p.text.find('Reported by') > -1) and (p.text.find('|') > -1):
                reported_on = p.text.split('|')[1].strip()
                for suffix in ['st', 'nd', 'rd', 'th']:
                    reported_on = reported_on.replace('%s,' % suffix,',')
                if reported_on.endswith('PM'):
                    delta = timedelta(hours=12)
                else:
                    delta = timedelta(hours=0)
                reported_on = reported_on[:-2].strip()
                reported_on = datetime.strptime(reported_on, '%B %d, %Y @ %H:%M') + delta
                break

    closed_on = None
    for div in soup.body.findAll('div', attrs={'class':'tcnt'}):
        for li in div.findAll('li'):
            if li.text.find('State changed from') > -1:
                ems = li.findAll('em', attrs={'class':'change'})
                if len(ems) >= 2:
                    em = ems[1] # changed from ... to ...
                    for status in ['hold', 'invalid', 'resolved']:
                        if em.text.find(status) > -1:
                            for span in div.findAll('span', attrs={'class':'event-date'}):
                                closed_on = span.a.text
    if closed_on:
        for suffix in ['st', 'nd', 'rd', 'th']:
            closed_on = closed_on.replace('%s,' % suffix,',')
        if closed_on.endswith('PM'):
            delta = timedelta(hours=12)
        else:
            delta = timedelta(hours=0)
        closed_on = closed_on[:-2].strip()
        closed_on = datetime.strptime(closed_on, '%B %d, %Y @ %H:%M') + delta


    return (title, reported_on, closed_on)

def extract_rt(title, soup):
    title = re.findall('Bug #\d+ for .*: (.*)', title)[0]

    reported_on = None
    closed_on = None

    for hist in soup.findAll('div', attrs={'class': 'history'}):
        for meta in hist.findAll('div', attrs={'class' : 'metadata'}):
            desc = meta.findAll('span', attrs={'class' : 'description'})[0].text.strip()
            date = meta.findAll('span', attrs={'class' : 'date'})[0].text.strip().replace('&nbsp;', ' ')
            try:
                created = re.findall('.*Ticket created', desc)[0]
                reported_on = date
                reported_on = datetime.strptime(reported_on, '%a %b %d %H:%M:%S %Y')
            except IndexError:
                pass

            try:
                closed = re.findall(".*Status changed from.*open.*to.*resolved", desc)[0]
                closed_on = date
                closed_on = datetime.strptime(closed_on, '%a %b %d %H:%M:%S %Y')
            except IndexError:
                pass


    return (title, reported_on, closed_on)


def extract_plone_title(title):
    return re.findall(u'(.*) \u2014 Plone CMS:', title)[0]

def extract_rt_perl_org_title(title):
    return re.findall('#\d+:(.*)', title)[0]

def extract_yui_title(title):
    return re.findall('#\d+(.*):: YUI 3.*', title)[0]

def extract_pear_php_net_title(title):
    try:
        return re.findall('Bug #\d+ ::(.*)', title)[0]
    except IndexError:
        return re.findall('Request #\d+ ::(.*)', title)[0]

def extract_rubyforge_title(title):
    return re.findall('RubyForge:.*: Detail: \d+(.*)', title)[0]

def extract_redmine_title(title):
    return re.findall('.* #\d+: (.*) - .* - .*', title)[0]

def extract_logilab_org_title(title):
    return re.findall('.* #\d+ (.*) \(Logilab.org\)', title)[0]

def extract_jira_title(soup):
    try:
        try:
            return soup.body.findAll('h1', attrs={'id' : 'summary-val'})[0].a.text
        except:
            # https://jira.mongodb.org/browse/RUBY-462 - not a link
            return soup.body.findAll('h1', attrs={'id' : 'summary-val'})[0].text
    except:
        return soup.body.findAll('h2', attrs={'id' : 'issue_header_summary'})[0].a.text

def extract_launchpad(title, soup):
    title = soup.body.findAll('h1', attrs={'id' : 'edit-title'})[0].span.text

    reported_on = soup.body.findAll('div', attrs={'id':'registration'})[0].span['title']
    reported_on = reported_on[:19]
    reported_on = datetime.strptime(reported_on, '%Y-%m-%d %H:%M:%S')

    closed_on = None
    for div in soup.body.findAll('div', attrs={'class':"boardCommentDetails"}):
        # comments have <time> tags
        for time in div.findAll('time'):
            closed_on = time['title']

        # actions OTOH have <span> tags
        if div.span:
            closed_on = div.span['title']

    if closed_on: # could be None for NEW bugs
        closed_on = closed_on[:19]
        closed_on = datetime.strptime(closed_on, '%Y-%m-%d %H:%M:%S')


    return (title, reported_on, closed_on)

def extract_wincent_title(soup):
    title = None
    reported_on = None
    closed_on = None
    is_closed = False

    for tr in soup.body.findAll('tr'):
        if tr.th.text == "Summary":
            title = tr.td.text

        if tr.th.text == "When":
            time = tr.td.findAll('time')
            reported_on = datetime.strptime(time[0].text, '%Y-%m-%dT%H:%M:%SZ')

    for ol in soup.body.findAll('ol', attrs={'id':'comments'}):
        for li in ol.findAll('li', attrs={'class' : 'comment admin'}):
            for ul in li.findAll('ul'):
                if ul.text == "From:newTo:closed":
                    closed_on = datetime.strptime(li.findAll('time')[0].text, '%Y-%m-%dT%H:%M:%SZ')

    return (title, reported_on, closed_on)


def extract_title_and_dates_from_html(page, type):
    soup = BeautifulSoup(page)
    title = soup.title.text # here's the title
    reported_on = None
    closed_on = None

    if type == BUG_TYPE_GITHUB:
        (title, reported_on, closed_on) = extract_github(title, soup)
    elif type == BUG_TYPE_BUGZILLA:
        (title, reported_on, closed_on) = extract_bugzilla(title, soup)
    elif type == BUG_TYPE_BITBUCKET:
        (title, reported_on, closed_on) = extract_bitbucket(title, soup)
    elif type == BUG_TYPE_LAUNCHPAD:
        (title, reported_on, closed_on) = extract_launchpad(title, soup)
    elif type == BUG_TYPE_GOOGLE:
        (title, reported_on, closed_on) = extract_google(title, soup)
    elif type == BUG_TYPE_TRAC:
        (title, reported_on, closed_on) = extract_trac(title, soup)
    elif type == BUG_TYPE_ROUNDUP:
        (title, reported_on, closed_on) = extract_roundup(title, soup)
    elif type == BUG_TYPE_SOURCEFORGE:
        (title, reported_on, closed_on) = extract_sourceforge(title, soup)
    elif type == BUG_TYPE_LIGHTHOUSE:
        (title, reported_on, closed_on) = extract_lighthouse(title, soup)
    elif type == BUG_TYPE_RT:
        (title, reported_on, closed_on) = extract_rt(title, soup)
    elif type == BUG_TYPE_PLONE:
        title = extract_plone_title(title)
    elif type == BUG_TYPE_RT_PERL_ORG:
        title = extract_rt_perl_org_title(title)
    elif type == BUG_TYPE_YUI_TRACKER:
        title = extract_yui_title(title)
    elif type == BUG_TYPE_PIVOTAL_TRACKER:
        title = '' # Pivotal Tracker uses AJAX and we can't extract titles from it
    elif type == BUG_TYPE_PEAR_PHP_NET:
        title = extract_pear_php_net_title(title)
    elif type == BUG_TYPE_RUBYFORGE:
        title = extract_rubyforge_title(title)
    elif type == BUG_TYPE_REDMINE:
        title = extract_redmine_title(title)
    elif type == BUG_TYPE_LOGILAB_ORG:
        title = extract_logilab_org_title(title)
    elif type == BUG_TYPE_JIRA:
        title = extract_jira_title(soup)
    elif type == BUG_TYPE_WINCENT:
        (title, reported_on, closed_on) = extract_wincent_title(soup)


    return (title.strip(), reported_on, closed_on)


def get_bug_format_string(homepage):
    """
        Construct the issues format string based on homepage.
    """

    if homepage.find('://github.com') > -1:  # toplevel GitHub page
        p = homepage.split('/')
        return 'https://github.com/%s/%s' % (p[3], p[4]) + '/issues/%d'
    elif homepage.find('.github.com') > -1:  # GitHub project pages
        p = homepage.split('/')
        u = p[2].split('.')[0]
        return 'https://github.com/%s/%s' % (u, p[3]) + '/issues/%d'
    elif homepage.find('://bitbucket.org') > -1:
        p = homepage.split('/')
        return 'https://bitbucket.org/%s/%s' % (p[3], p[4]) + '/issue/%d'
    elif homepage.find('://code.google.com/p') > -1:
        p = homepage.split('/')
        return 'http://code.google.com/p/%s/issues/detail?id=' % p[4] + '%d'
    else:
        return None

def normalize_bug_format_string(bugurl):
    """
        Contruct the format string from the main Bugtracker URL
    """

    # many packages (e.g.Ruby) point to the github issues pages
    # get_bug_format_string will do the right thing
    format_str = get_bug_format_string(bugurl)

    if bugurl.find('rt.cpan.org') > -1:
        format_str = 'https://rt.cpan.org/Public/Bug/Display.html?id=%d'
    elif bugurl.find('rt.perl.org') > -1:
        format_str = 'https://rt.perl.org/rt3/Public/Bug/Display.html?id=%d'

    return format_str or bugurl


def get_bug_type(bugurl, old_type = None):
    """
        Return bug tracker type.
    """

    if bugurl is None:
        return BUG_TYPE_UNKNOWN

    if bugurl.find('github.com') > -1:
        return BUG_TYPE_GITHUB
    elif bugurl.find('bugzilla') > -1:
        return BUG_TYPE_BUGZILLA
    elif bugurl.find('bitbucket.org') > -1:
        return BUG_TYPE_BITBUCKET
    elif bugurl.find('launchpad.net') > -1:
        return BUG_TYPE_LAUNCHPAD
    elif bugurl.find('code.google.com') > -1:
        return BUG_TYPE_GOOGLE
    elif bugurl.find('bugs.python.org') > -1:
        return BUG_TYPE_ROUNDUP
    elif bugurl.find('rt.cpan.org') > -1:
        return BUG_TYPE_RT
    elif bugurl.find('rt.perl.org') > -1:
        return BUG_TYPE_RT_PERL_ORG
    elif bugurl.find('sourceforge.net') > -1:
        # SourceForge now supports Trac too
        if bugurl.find('trac') > -1:
            return BUG_TYPE_TRAC
        else:
            return BUG_TYPE_SOURCEFORGE
    elif bugurl.find('pivotaltracker.com') > -1:
        return BUG_TYPE_PIVOTAL_TRACKER
#    elif bugurl.find('plone.org') > -1:
#        return BUG_TYPE_PLONE
    elif bugurl.find('https://dev.plone.org') > -1:
        return BUG_TYPE_TRAC
    elif bugurl.find('pear.php.net') > -1:
        return BUG_TYPE_PEAR_PHP_NET
    elif bugurl.find('rubyforge.org') > -1:
        return BUG_TYPE_RUBYFORGE
    elif bugurl.find('bugs.ruby-lang.org') > -1:
        return BUG_TYPE_REDMINE
    elif bugurl.find('logilab.org') > -1:
        return BUG_TYPE_LOGILAB_ORG
    elif bugurl.find('jira') > -1:
        return BUG_TYPE_JIRA
    elif bugurl.find('issues.jboss.org') > -1:
        return BUG_TYPE_JIRA
    elif bugurl.find('issues.apache.org') > -1:
        return BUG_TYPE_JIRA
# NB: always keep it last
    elif bugurl.find('trac') > -1:
        return BUG_TYPE_TRAC
    else:
        return old_type or BUG_TYPE_UNKNOWN

def get_bug_regexp():
    """
        Return a complex regular expression that will match all
        possible issue trackers.
    """

    exprs = [
        '#\d+',
        '#*gh-*\d+',
        '#*GH-*\d+',
        'ixed\s+#*\d+',
        'ssue\s*#*\d+',
        'issues/\d+',
        'bug\s*#*\d+',
        '\+bug/\d+',   # https://bugs.launchpad.net/zope.tales/+bug/1002242
        '\[bug=\d+\]', # Patch by Aaron Devore. [bug=1038301] BeautifulSoup4
        'RT\s*#*\s*\d+',
#        'rt\s*\d+,*', # matches port 1234
        'ticket/\\d+',
        '\?id=\d+',
        '\[rt.cpan.org \d+\]',
        'rt.cpan.org \d+',
        '\[github \d+\]',
        '\[googlecode \d+\]',
#        '\*\s+\d+',   # matches bulleted lists in Markdown
        'LP\d+',
        '\[\s+\d+\s+\]',
        '\[ticket:\d+\]', # [ticket:2480]
        '[A-Z]+-\d+',     # [HV-123], [#SPR-123], JAVA-555 - commonly used for Java projects
        'ghpull:`\d+`',
        'ghissue:`\d+`',
        'issue:`\d+`', # boto release notes
        ]

    rx = "#\d+" # repeat so we can get a clean expression
    for e in exprs:
        rx = rx + "|" + e

#    print rx

    return re.compile(rx)

if __name__ == "__main__":
    from utils import fetch_page
# NB: order is the same as in extract_title_and_dates_from_html()


    print extract_title_and_dates_from_html(fetch_page('https://github.com/cowboyd/therubyracer/pull/240'), BUG_TYPE_GITHUB)
    print extract_title_and_dates_from_html(fetch_page('https://github.com/boto/boto/issues/1757'), BUG_TYPE_GITHUB)
    print extract_title_and_dates_from_html(fetch_page('https://github.com/marcandre/backports/pull/63'), BUG_TYPE_GITHUB)
    print extract_title_and_dates_from_html(fetch_page('https://github.com/boto/boto/pull/407'), BUG_TYPE_GITHUB)
    print extract_title_and_dates_from_html(fetch_page('https://github.com/hmarr/django-ses/pull/40'), BUG_TYPE_GITHUB)
    print extract_title_and_dates_from_html(fetch_page('https://github.com/schacon/hg-git/issues/31'), BUG_TYPE_GITHUB)

#    print extract_title_and_dates_from_html(fetch_page('https://bugzilla.redhat.com/show_bug.cgi?id=800754'), BUG_TYPE_BUGZILLA)

#    print extract_title_and_dates_from_html(fetch_page('https://bitbucket.org/birkenfeld/pygments-main/issue/763'), BUG_TYPE_BITBUCKET)
#    print extract_title_and_dates_from_html(fetch_page('https://bitbucket.org/birkenfeld/pygments-main/issue/861'), BUG_TYPE_BITBUCKET)

#    print extract_title_and_dates_from_html(fetch_page('https://bugs.launchpad.net/pytz/+bug/207604'), BUG_TYPE_LAUNCHPAD)

#    print extract_title_and_dates_from_html(fetch_page('http://code.google.com/p/pysqlite/issues/detail?id=11'), BUG_TYPE_GOOGLE)
#    print extract_title_and_dates_from_html(fetch_page('http://code.google.com/p/pysqlite/issues/detail?id=23'), BUG_TYPE_GOOGLE)
#    print extract_title_and_dates_from_html(fetch_page('http://code.google.com/p/geopy/issues/detail?id=2'), BUG_TYPE_GOOGLE)


#    print extract_title_and_dates_from_html(fetch_page('http://www.sqlalchemy.org/trac/ticket/695'), BUG_TYPE_TRAC)
#    print extract_title_and_dates_from_html(fetch_page('http://www.sqlalchemy.org/trac/ticket/1635'), BUG_TYPE_TRAC)
#    print extract_title_and_dates_from_html(fetch_page('https://code.djangoproject.com/ticket/18436'), BUG_TYPE_TRAC)


#    print extract_title_and_dates_from_html(fetch_page('http://bugs.repoze.org/issue4'),  BUG_TYPE_ROUNDUP)
#    print extract_title_and_dates_from_html(fetch_page('http://bugs.repoze.org/issue85'), BUG_TYPE_ROUNDUP)
#    print extract_title_and_dates_from_html(fetch_page('http://bugs.repoze.org/issue43'), BUG_TYPE_ROUNDUP)

#    print extract_title_and_dates_from_html(fetch_page('http://sourceforge.net/tracker/?func=detail&aid=3552403&group_id=38414&atid=422030'), BUG_TYPE_SOURCEFORGE)
#    print extract_title_and_dates_from_html(fetch_page('http://sourceforge.net/p/pydev/bugs/1558/'), BUG_TYPE_SOURCEFORGE)

#    print extract_title_and_dates_from_html(fetch_page('http://psycopg.lighthouseapp.com/projects/62710/tickets/83'), BUG_TYPE_LIGHTHOUSE)
#    print extract_title_and_dates_from_html(fetch_page('http://psycopg.lighthouseapp.com/projects/62710/tickets/78'), BUG_TYPE_LIGHTHOUSE)
#    print extract_title_and_dates_from_html(fetch_page('http://psycopg.lighthouseapp.com/projects/62710/tickets/146'), BUG_TYPE_LIGHTHOUSE)
#    print extract_title_and_dates_from_html(fetch_page('http://psycopg.lighthouseapp.com/projects/62710/tickets/112'), BUG_TYPE_LIGHTHOUSE)

#    print extract_title_and_dates_from_html(fetch_page('https://rt.cpan.org/Public/Bug/Display.html?id=72096'), BUG_TYPE_RT)
#    print extract_title_and_dates_from_html(fetch_page('https://rt.cpan.org/Public/Bug/Display.html?id=86007'), BUG_TYPE_RT)

#    print extract_title_and_dates_from_html(fetch_page('https://wincent.com/issues/1955'), BUG_TYPE_WINCENT)



