################################################################################
#
#   Copyright (c) 2011-2014, Alexander Todorov <atodorov@nospam.dif.io>
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

import cpan
import pypi
import pear
import pear2
import nodejs
import github
import rubygems
import packagist
import mavencentral

import os
import sys
import bugs
import utils
from django.db import models
from datetime import datetime
from settings import STATIC_URL
from utils import URL_ADVISORIES
from django.db.models import Manager
from django.contrib.auth.models import User
from managers import SkinnyManager

try:
    from settings import FQDN
except:
    FQDN=""

try:
    from settings import APPLICATION_DB_TABLE
except:
    APPLICATION_DB_TABLE = False

try:
    from settings import PACKAGE_DB_TABLE
except:
    PACKAGE_DB_TABLE = False

try:
    from settings import PACKAGE_VERSION_DB_TABLE
except:
    PACKAGE_VERSION_DB_TABLE = False

try:
    from settings import INSTALLED_PACKAGE_DB_TABLE
except:
    INSTALLED_PACKAGE_DB_TABLE = False

try:
    from settings import ADVISORY_DB_TABLE
except:
    ADVISORY_DB_TABLE = False

# Cloud providers
VENDOR_OPENSHIFT_EXPRESS=0
VENDOR_DOTCLOUD=1
VENDOR_HEROKU=2
VENDOR_CLOUDCONTROL=3
VENDOR_APPFOG=4

# Generic vendors
VENDOR_VIRTUALENV=1000

VENDOR_MANUAL_IMPORT=10000

# used in Django Admin and in
# application dashboard
VENDOR_TYPES = (
    (VENDOR_OPENSHIFT_EXPRESS, 'OpenShift'),
    (VENDOR_DOTCLOUD, 'dotCloud'),
    (VENDOR_HEROKU, 'Heroku'),
    (VENDOR_CLOUDCONTROL, 'cloudControl'),
    (VENDOR_APPFOG, 'AppFog'),
    (VENDOR_VIRTUALENV, 'virtualenv'),
    (VENDOR_MANUAL_IMPORT, 'Manual import'),
)

APP_STATUS_REMOVED=-10
APP_STATUS_IMPORTING=-5
APP_STATUS_PENDING=0

# NB: Always keep working states > 0
# since the UI hard codes this
APP_STATUS_APPROVED=10
APP_STATUS_UPTODATE=20
APP_STATUS_NEEDSUPDATE=30

STATUS_TYPES = (
    (APP_STATUS_REMOVED, 'Removed'),
    (APP_STATUS_IMPORTING, 'Importing'),
    (APP_STATUS_PENDING, 'Pending'),
    (APP_STATUS_APPROVED, 'Approved'),
    (APP_STATUS_UPTODATE, 'Up to date'),
    (APP_STATUS_NEEDSUPDATE, 'Needs update'),
)

class Application(models.Model):
    '''
        Stores information about tracked applications
    '''

    # override default QuerySet manager
    objects = SkinnyManager()

    class Meta:
        if APPLICATION_DB_TABLE:
            db_table = APPLICATION_DB_TABLE

    owner = models.ForeignKey(User, unique=False)
    name = models.CharField(max_length=128)
    uuid = models.CharField(max_length=64)
    type = models.CharField(max_length=32)
    vendor = models.IntegerField(choices=VENDOR_TYPES)
    status = models.IntegerField(choices=STATUS_TYPES, db_index=True)
    last_checkin = models.DateTimeField(null=True, blank=True, db_index=True)
    date_approved = models.DateTimeField(null=True, blank=True, db_index=True)
    date_removed = models.DateTimeField(null=True, blank=True)
    url = models.URLField()

    def __unicode__(self):
        return unicode(self.name)


    def type_img_48_url(self):
        """
            Return the URL with icon for this application
            Size: 48x48 px
        """
        img_id = None
        type_lower = self.type.lower()

        if type_lower.find('python') > -1:
            img_id = PYPI_PYTHON_PKG
        elif type_lower.find('ruby') > -1:
            img_id = RUBYGEM_RUBY_PKG
        elif type_lower.find('node') > -1:
            img_id = NODEJS_PKG
        elif type_lower.find('java') > -1:
            img_id = "java"
        elif type_lower.find('perl') > -1:
            img_id = PERL_CPAN_PKG
        elif type_lower.find('php') > -1:
            img_id = "php"

        return "%si/p/t/48/%s.png" % (STATIC_URL, img_id)

# NB: values are hard-coded into the client code
# Do not change, Update only
PYPI_PYTHON_PKG   =    0
RUBYGEM_RUBY_PKG  =    1
NODEJS_PKG        =    2
JAVA_MAVEN_PKG    =  300
PERL_CPAN_PKG     =  400
PHP_PEAR_PKG      =  500
PHP_PEAR2_PKG     =  501
PHP_PACKAGIST_PKG =  600
GITHUB_TAGGED_PKG = 2000

# used for Django Admin
PACKAGE_TYPES = (
    (PYPI_PYTHON_PKG, 'Python'),
    (RUBYGEM_RUBY_PKG, 'Ruby'),
    (NODEJS_PKG, 'Node.js'),
    (JAVA_MAVEN_PKG, 'Java'),
    (PERL_CPAN_PKG, 'Perl'),
    (PHP_PEAR_PKG, 'PHP'),
    (PHP_PEAR2_PKG, 'PHP'),
    (PHP_PACKAGIST_PKG, 'PHP'),
    (GITHUB_TAGGED_PKG, 'GitHub project'),
)


# Used to get the proper callbacks
PACKAGE_CALLBACKS = {
    PYPI_PYTHON_PKG: {
            'compare_versions' : pypi.compare_versions,
            'get_url' : pypi.get_url,
            'get_latest' : pypi.get_latest,
            'find_date' : pypi.get_release_date,
            'get_download_url' : pypi.get_download_url,
            'get_latest_packages_from_rss' : pypi.get_latest_from_rss,
        },
    RUBYGEM_RUBY_PKG: {
            'compare_versions' : rubygems.compare_versions,
            'get_url' : rubygems.get_url,
            'get_latest' : rubygems.get_latest,
            'find_date' : rubygems.get_release_date,
            'get_download_url' : rubygems.get_download_url,
# Since 2012-11-16, 12:00:00 Ruby gems are imported view webhook
# this decreases the number of duplicate messges for already imported packages
            'get_latest_packages_from_rss' : None, # rubygems.get_latest_from_rss,
        },
    NODEJS_PKG: {
            'compare_versions' : nodejs.compare_versions,
            'get_url' : nodejs.get_url,
            'get_latest' : nodejs.get_latest,
            'find_date' : nodejs.get_release_date,
            'get_download_url' : nodejs.get_download_url,
            'get_latest_packages_from_rss' : nodejs.get_latest_from_rss,
        },
    JAVA_MAVEN_PKG: {
            'compare_versions' : None,
            'get_url' : mavencentral.get_url,
            'get_latest' : mavencentral.get_latest,
            'find_date' : mavencentral.get_release_date,
            'get_download_url' : mavencentral.get_download_url,
            'get_latest_packages_from_rss' : mavencentral.get_latest_from_rss,
        },
    PERL_CPAN_PKG: {
            'compare_versions' : None,
            'get_url' : cpan.get_url,
            'get_latest' : cpan.get_latest,
            'find_date' : cpan.get_release_date,
            'get_download_url' : cpan.get_download_url,
            'get_latest_packages_from_rss' : cpan.get_latest_from_rss,
        },
    PHP_PEAR_PKG: {
            'compare_versions' : None,
            'get_url' : pear.get_url,
            'get_latest' : pear.get_latest,
            'find_date' : pear.get_release_date,
            'get_download_url' : pear.get_download_url,
            'get_latest_packages_from_rss' : pear.get_latest_from_rss,
        },
    PHP_PEAR2_PKG: {
            'compare_versions' : None,
            'get_url' : pear2.get_url,
            'get_latest' : pear2.get_latest,
            'find_date' : pear2.get_release_date,
            'get_download_url' : pear2.get_download_url,
            'get_latest_packages_from_rss' : pear2.get_latest_from_rss,
        },
    PHP_PACKAGIST_PKG: {
            'compare_versions' : None,
            'get_url' : packagist.get_url,
            'get_latest' : packagist.get_latest,
            'find_date' : packagist.get_release_date,
            'get_download_url' : packagist.get_download_url,
            'get_latest_packages_from_rss' : packagist.get_latest_from_rss,
        },
    GITHUB_TAGGED_PKG: {
            'compare_versions' : None,
            'get_url' : github.get_url,
            'get_latest' : github.get_latest_from_tag,
            'find_date' : github.get_release_date_from_tag,
            'get_download_url' : github.get_download_url_from_tag,
            'get_latest_packages_from_rss' : None,
        },
}


# used for Package, PackageVersion and Advisory
STATUS_DROPPED = -10
STATUS_NEW = 0
STATUS_MODIFIED = 5
STATUS_ASSIGNED = 10
STATUS_VERIFIED = 20
STATUS_PUSH_READY = 30
STATUS_LIVE = 40

PACKAGE_STATUSES = (
    (STATUS_NEW, 'NEW'),           # new package submitted to DB. Not processed by a person
    (STATUS_MODIFIED, 'MODIFIED'), # automatically modified, e.g. by cron
    (STATUS_ASSIGNED, 'ASSIGNED'), # assigned to somebody to collect website, source url, etc.
    (STATUS_VERIFIED, 'VERIFIED'), # all information has been collected and verified
)

#NB: The names are displayed on the public site
BUG_TRACKER_CHOICES = (
    (bugs.BUG_TYPE_NONE, "N/A"),
    (bugs.BUG_TYPE_UNKNOWN, "Unknown"),
    (bugs.BUG_TYPE_GITHUB, "GitHub"),
    (bugs.BUG_TYPE_BUGZILLA, "Bugzilla"),
    (bugs.BUG_TYPE_BITBUCKET, "Bitbucket"),
    (bugs.BUG_TYPE_LAUNCHPAD, "Launchpad"),
    (bugs.BUG_TYPE_GOOGLE, "Google Code"),
    (bugs.BUG_TYPE_TRAC, "Trac"),
    (bugs.BUG_TYPE_ROUNDUP, "Roundup Issue Tracker"),
    (bugs.BUG_TYPE_SOURCEFORGE, "SourceForge.net"),
    (bugs.BUG_TYPE_LIGHTHOUSE, "Lighthouse"),
    (bugs.BUG_TYPE_RT, "RT: Request Tracker"),
    (bugs.BUG_TYPE_PLONE, "Plone"),
    (bugs.BUG_TYPE_RT_PERL_ORG, "RT: rt.perl.org"),
    (bugs.BUG_TYPE_YUI_TRACKER, "YUI Library tracker"),
    (bugs.BUG_TYPE_PIVOTAL_TRACKER, "Pivotal Tracker"),
    (bugs.BUG_TYPE_PEAR_PHP_NET, "pear.php.net bug tracker"),
    (bugs.BUG_TYPE_RUBYFORGE, "RubyForge.org bug tracker"),
    (bugs.BUG_TYPE_REDMINE, "Redmine"),
    (bugs.BUG_TYPE_LOGILAB_ORG, "Logilab.org/CubicWeb"),
    (bugs.BUG_TYPE_JIRA, "Jira"),
    (bugs.BUG_TYPE_WINCENT, "wincent.com"),
)

#NB: The names are displayed on the public site
SCM_TYPES = (
    (utils.SCM_UNKNOWN, "Unknown"),
    (utils.SCM_GIT, "Git"),
    (utils.SCM_MERCURIAL, "Mercurial"),
    (utils.SCM_BAZAAR, "Bazaar"),
    (utils.SCM_SUBVERSION, "Subversion"),
    (utils.SCM_CVS, "CVS"),
    (utils.SCM_METACPAN, "metacpan.org"),
    (utils.SCM_TARBALL, "Tarball (.tar.gz, .tar.bz2, .tgz)"),
)

# used for directory naming and such
SCM_SHORT_NAMES = {
    utils.SCM_GIT : 'git',
    utils.SCM_MERCURIAL : 'hg',
    utils.SCM_BAZAAR : 'bzr',
    utils.SCM_SUBVERSION : 'svn',
    utils.SCM_CVS : 'cvs',
    utils.SCM_METACPAN : 'metacpan',
    utils.SCM_TARBALL : 'tarball',
    utils.SCM_APIGEN : 'api',
    utils.SCM_MAGIC : 'magic',
}

# used below to construct paths to the bin directory
LOCAL_DIR = os.path.dirname(os.path.realpath(__file__))

HGBIN = 'hg'
HG_DIFF_PLUS_STAT = LOCAL_DIR + '/bin/hg_diff_stat'
BZRBIN = 'bzr'
BZR_DIFFSTAT = LOCAL_DIR + '/bin/bzr-diffstat'
BZR_DIFF_PLUS_STAT = LOCAL_DIR + '/bin/bzr_diff_stat'
DIFF_METACPAN_BIN = LOCAL_DIR + '/diff_metacpan'

# make use of the locally installed bzr/hg if possible
if os.environ.has_key('OPENSHIFT_HOMEDIR'):
    # we're on OpenShift - not running the workers there usually
    HGBIN  = os.environ['OPENSHIFT_HOMEDIR'] + '/python-2.6/virtenv/bin/' + HGBIN
    BZRBIN = os.environ['OPENSHIFT_HOMEDIR'] + '/python-2.6/virtenv/bin/' + BZRBIN
elif hasattr(sys, 'real_prefix') and os.path.exists(sys.prefix+'/bin/'):
    # we're inside a virtualenv and process was started with ~/.virtualenv/name/bin/python script.py
    HGBIN  = sys.prefix + '/bin/' + HGBIN
    HG_DIFF_PLUS_STAT = "%s/bin/python %s" % (sys.prefix, HG_DIFF_PLUS_STAT)
    BZRBIN = sys.prefix + '/bin/' + BZRBIN
#    BZR_DIFFSTAT =  "%s/bin/python %s" % (sys.prefix, BZR_DIFFSTAT)
    BZR_DIFF_PLUS_STAT = "%s/bin/python %s" % (sys.prefix, BZR_DIFF_PLUS_STAT)
    DIFF_METACPAN_BIN =  "%s/bin/python %s" % (sys.prefix, DIFF_METACPAN_BIN)
elif os.environ.has_key('HOME') and os.path.exists(os.environ['HOME']+'/.virtualenvs/difio/bin/'):
    # $HOME is defined - try to find a sane virtualenv
    # NB: $HOME is not defined when `service celeryd start` is run
    HGBIN  = os.environ['HOME'] + '/.virtualenvs/difio/bin/' + HGBIN
    BZRBIN = os.environ['HOME'] + '/.virtualenvs/difio/bin/' + BZRBIN

# clone/checkout commands
# arguments are <scmurl> <directory>
SCM_CLONE_CMD = {
    utils.SCM_GIT : 'git clone %s %s',
    utils.SCM_MERCURIAL : HGBIN + ' clone %s %s',
    utils.SCM_BAZAAR : BZRBIN + ' branch --use-existing-dir %s %s',
    utils.SCM_SUBVERSION : 'svn checkout --non-interactive --trust-server-cert %s %s',
    utils.SCM_CVS : 'cvs %s && mv cvstmp %s',  # -z6 -d:pserver:anonymous@python-ldap.cvs.sourceforge.net:/cvsroot/python-ldap co -d cvstmp -P python-ldap
    utils.SCM_METACPAN : None,
    utils.SCM_TARBALL : 'echo %s >/dev/null; cd %s && git init',
    utils.SCM_APIGEN : 'echo %s >/dev/null; cd %s && git init',
}

# pull/update sources
SCM_PULL_CMD = {
    utils.SCM_GIT : 'git pull && git fetch --tags',
    utils.SCM_MERCURIAL : HGBIN + ' pull',
    utils.SCM_BAZAAR : BZRBIN + ' merge',
    utils.SCM_SUBVERSION : 'svn update --non-interactive --trust-server-cert',
    utils.SCM_CVS : 'cvs update -dPA',
    utils.SCM_METACPAN : None,
    utils.SCM_TARBALL : None,
    utils.SCM_APIGEN : None,
}

# diff changelog
# arguments <old-rev> <new-rev> <changelog>
SCM_DIFF_CHANGELOG_CMD = {
    utils.SCM_GIT : 'git diff -M %s..%s -- %s',
    utils.SCM_MERCURIAL : HGBIN + ' diff -r %s -r %s %s',
    utils.SCM_BAZAAR : BZRBIN + ' diff -r %s..%s %s',
    utils.SCM_SUBVERSION : 'svn diff --non-interactive --trust-server-cert -r %s:%s %s',
    utils.SCM_CVS : 'cvs diff -u -r %s -r %s %s',
    utils.SCM_METACPAN : DIFF_METACPAN_BIN + ' %s %s %s',
    utils.SCM_APIGEN : None,
}
SCM_DIFF_CHANGELOG_CMD[utils.SCM_TARBALL] = SCM_DIFF_CHANGELOG_CMD[utils.SCM_GIT]


# diff all files
# arguments <old-rev> <new-rev>
SCM_DIFF_ALL_CMD = {
    utils.SCM_GIT : 'git diff -M %s..%s',
    utils.SCM_MERCURIAL : HGBIN + ' diff -r %s -r %s',
    utils.SCM_BAZAAR : BZRBIN + ' diff -r %s..%s',
    utils.SCM_SUBVERSION : 'svn diff --non-interactive --trust-server-cert -r %s:%s',
    utils.SCM_CVS : 'cvs diff -u -r %s -r %s',
    utils.SCM_METACPAN : DIFF_METACPAN_BIN + ' %s %s',
}
SCM_DIFF_ALL_CMD[utils.SCM_TARBALL] = SCM_DIFF_ALL_CMD[utils.SCM_GIT]
SCM_DIFF_ALL_CMD[utils.SCM_APIGEN] = 'git diff -M -u --stat %s..%s'

# diff stat shows full stat.
# arguments <old-rev> <new-rev>
SCM_DIFF_STAT_CMD = {
    utils.SCM_GIT : 'git diff --stat -M %s..%s',
    utils.SCM_MERCURIAL : HGBIN + ' diff --stat -r %s -r %s',
    utils.SCM_BAZAAR : BZR_DIFF_PLUS_STAT + ' ' + BZR_DIFFSTAT + ' %s %s 1',
#todo add diff summary below
    utils.SCM_SUBVERSION : None, # "svn diff -r %s:%s --summarize", # doesn't print totals at the end
    utils.SCM_CVS : None,
    utils.SCM_METACPAN : None, # todo: fix me
}
SCM_DIFF_STAT_CMD[utils.SCM_TARBALL] = SCM_DIFF_STAT_CMD[utils.SCM_GIT]
SCM_DIFF_STAT_CMD[utils.SCM_APIGEN] = 'git diff -M --shortstat %s..%s'

# get commit log
# arguments <old-rev> <new-rev>
SCM_LOG_CMD = {
    utils.SCM_GIT : 'git log %s..%s',
    utils.SCM_MERCURIAL : HGBIN + ' log -r %s:%s',
    utils.SCM_BAZAAR : BZRBIN + ' log -r %s..%s',
    utils.SCM_SUBVERSION : 'svn log --non-interactive --trust-server-cert -r %s:%s',
    utils.SCM_CVS : 'cvs log -r %s:%s *',
    utils.SCM_METACPAN : None,
    utils.SCM_TARBALL : None,
    utils.SCM_APIGEN : None,
}

# get commit log under particular path
# arguments <old-rev> <new-rev> <path>
SCM_LOG_PATH_CMD = {
    utils.SCM_GIT : 'git log %s..%s -- %s',
    utils.SCM_MERCURIAL : HGBIN + ' log -r %s:%s %s',
    utils.SCM_BAZAAR : BZRBIN + ' log -r %s..%s %s',
    utils.SCM_SUBVERSION : 'svn log --non-interactive --trust-server-cert -r %s:%s %s',
    utils.SCM_CVS : 'cvs log -r %s:%s %s',
    utils.SCM_METACPAN : None,
    utils.SCM_TARBALL : None,
    utils.SCM_APIGEN : None,
}

# list tags commands
SCM_LIST_TAGS_CMD = {
    utils.SCM_GIT : 'git tag', # this is inacurate 'for t in `git tag`; do sha=`git show --format=format:"%H" $t`; echo $t,$sha | cut -f1 -d" "; done',
    utils.SCM_MERCURIAL : HGBIN + ' tags',
    utils.SCM_BAZAAR : BZRBIN + ' tags',
    utils.SCM_SUBVERSION : None,
    utils.SCM_CVS : None,
    utils.SCM_METACPAN : None,
    utils.SCM_TARBALL : None,
    utils.SCM_APIGEN : None,
}

class Package(models.Model):
    '''
        Stores information about software package
    '''

    # override default QuerySet manager
    objects = SkinnyManager()

    class Meta:
        permissions = (
            ("package_modify_all", "Can modify all fields"),
        )
        if PACKAGE_DB_TABLE:
            db_table = PACKAGE_DB_TABLE

    name = models.CharField(max_length=128, blank=True, db_index=True)
    type = models.IntegerField('Package Type', choices=PACKAGE_TYPES, null=True, blank=True, db_index=True)
    website = models.URLField(null=True, blank=True)
    scmurl = models.CharField('URL to check-out source', max_length=256, null=True, blank=True)
    scmurl.help_text = "For example git read-only url. NB: if SCM Type is Tarball then URL is N/A"
    scmtype = models.IntegerField('Type of SCM', choices=SCM_TYPES, default=utils.SCM_UNKNOWN, db_index=True)

    bugurl = models.CharField('Format string for bug URLs', max_length=256, null=True, blank=True)
    bugurl.help_text = 'e.g. http://bugzilla.redhat.com/%d'

    bugtype = models.IntegerField('Bug tracker type', choices=BUG_TRACKER_CHOICES, default=bugs.BUG_TYPE_UNKNOWN, db_index=True)

    changelog = models.CharField('Name of change log file', max_length=256, null=True, blank=True)
    changelog.help_text = 'This is used to automatically generate details about an advisory'

    status = models.IntegerField(choices=PACKAGE_STATUSES, default=STATUS_NEW, db_index=True)
    assigned_to = models.CharField(blank=True, null=True, max_length=64)
    last_checked = models.DateTimeField(null=True, blank=True, default=datetime(2000, 01, 01), db_index=True)

    # this is set automatically and used when searching to display updates
    # it is always set to the latest according to package specific version sorting function
    latest_version = models.CharField(max_length=64, null=True, blank=True)

    # used for multiple subpackages in the same repo
    subpackage_path = models.CharField(max_length=256, null=True, blank=True)

    # when added to DB. used internally wrt manual Package additions
    added_on = models.DateTimeField(db_index=True, default=datetime.now())

    def __unicode__(self):
        return unicode(self.name)


    def index_url(self):
        """
            Return the URL in the package index.
        """
        if self.type == PYPI_PYTHON_PKG:
            return "https://pypi.python.org/pypi/%s" % pypi._other_name(self.name)
        elif self.type == RUBYGEM_RUBY_PKG:
            return "https://rubygems.org/gems/%s" % self.name
        elif self.type == NODEJS_PKG:
            return "https://npmjs.org/package/%s" % self.name
        elif self.type == JAVA_MAVEN_PKG:
            [gid, aid] = mavencentral._groupid_artifactid(self.name)
            if self.latest_version:
                return "http://search.maven.org/#artifactdetails|%s|%s|%s|" % (gid, aid, self.latest_version)
            else:
                return "http://search.maven.org/#search|ga|1|g%%3A%%22%s%%22%%20AND%%20a%%3A%%22%s%%22" % (gid, aid)
        elif self.type == PERL_CPAN_PKG:
            return "https://metacpan.org/release/%s" % '-'.join(cpan._other_name(self.name).split('::'))
        elif self.type == PHP_PEAR_PKG:
            return "http://pear.php.net/package/%s" % self.name
        elif self.type == PHP_PEAR2_PKG:
            return "http://pear2.php.net/%s" % self.name
        elif self.type == PHP_PACKAGIST_PKG:
            return "https://packagist.org/packages/%s" % self.name
        elif self.type == GITHUB_TAGGED_PKG:
            return "https://github.com/%s" % self.name
        else:
            return "UNKNOWN"


    def type_img_48_url(self):
        """
            Return the URL with icon for this package type
            Size: 48x48 px
        """
        return "%si/p/t/48/%d.png" % (STATIC_URL, self.type)


PACKAGE_VERSION_STATUSES = (
    (STATUS_NEW, 'NEW'),           # new version found by automated tools. Not processed by a person
    (STATUS_MODIFIED, 'MODIFIED'), # automatically modified, e.g. by cron
    (STATUS_ASSIGNED, 'ASSIGNED'), # assigned to somebody to inspect and collect info
    (STATUS_VERIFIED, 'VERIFIED'), # all information has been collected and verified
)

class PackageVersion(models.Model):
    """
        Describes different versions of the same package
    """

    # override default QuerySet manager
    objects = SkinnyManager()

    class Meta:
        permissions = (
            ("packageversion_modify_all", "Can modify all fields"),
        )
        if PACKAGE_VERSION_DB_TABLE:
            db_table = PACKAGE_VERSION_DB_TABLE

    package = models.ForeignKey(Package, unique=False)
    version = models.CharField(max_length=64, db_index=True)
    scmid = models.CharField('Branch/tag/commit/revision for this version', max_length=128, null=True, blank=True)
    status = models.IntegerField(choices=PACKAGE_VERSION_STATUSES, default=STATUS_NEW, db_index=True)
    assigned_to = models.CharField(blank=True, null=True, max_length=64)
    released_on = models.DateTimeField(null=True, blank=True, db_index=True)
    download_url = models.CharField(blank=True, null=True, max_length=200)
    download_url.help_text = 'URL to package SOURCE, e.g. http://project.org/downloads/project-1.0.tar.gz'
    size = models.IntegerField('Size in bytes', default=None, null=True, blank=True)

    # when added to DB. used internally wrt manual PackageVersion additions
    added_on = models.DateTimeField(db_index=True, default=datetime.now())

    def __unicode__(self):
        return unicode("%s-%s" % (self.package, self.version))


class InstalledPackage(models.Model):
    """
        A package that is installed into an Application
    """

    # override default QuerySet manager
    objects = SkinnyManager()

    class Meta:
        if INSTALLED_PACKAGE_DB_TABLE:
            db_table = INSTALLED_PACKAGE_DB_TABLE

    # NB: no joins here
    application = models.IntegerField(null=False, db_index=True, default=0)
    owner   = models.IntegerField(null=False, db_index=True)
    package = models.IntegerField(null=False, db_index=True)
    version = models.IntegerField(null=False, db_index=True, default=0)



SEVERITY_TYPES = (
    (utils.SEVERITY_UNKNOWN, 'Unknown'),
    (utils.SEVERITY_LOW, 'Low'),
    (utils.SEVERITY_MEDIUM, 'Medium'),
    (utils.SEVERITY_HIGH, 'High'),
)


ADVISORY_STATUSES = (
    (STATUS_DROPPED, 'DROPPED'),   # DROPPED, NO_SHIP
    (STATUS_NEW, 'NEW'),           # new advisory generated by automated tools. Not processed by a person
    (STATUS_MODIFIED, 'MODIFIED'), # automatic collection of information has completed
    (STATUS_ASSIGNED, 'ASSIGNED'), # assigned to somebody to inspect and collect additional info
    (STATUS_PUSH_READY, 'PUSH_READY'), # all info collected and verified, ready to publish live
    (STATUS_LIVE, 'LIVE'),         # advisory has been pushed live already. the point of no return.
)


# See also:
# http://rhn.redhat.com/errata/RHBA-2011-1642.html
# https://rhn.redhat.com/errata/RHSA-2011-1323.html

class Advisory(models.Model):
    """
        Represents updates information between two versions of a package.
    """

    # override default QuerySet manager
    objects = SkinnyManager()

    class Meta:
        permissions = (
            ("advisory_modify_all", "Can modify all fields"),
            ("advisory_drop", "Can DROP advisories"),
        )
        if ADVISORY_DB_TABLE:
            db_table = ADVISORY_DB_TABLE

    old = models.ForeignKey(PackageVersion, unique=False, related_name='Old version')
    new = models.ForeignKey(PackageVersion, unique=False, related_name='New version')
#TODO: replace this with a string similarity index based on difflib.SequenceMatcher
# and then reverse utils.which_severity() b/c 100% means no changes, 0% means totally different
# and maybe remove this field altogether and add the data to more.json
    type = models.IntegerField('Change rate %', default=None, null=True, blank=True)
#    type.help_text = "NB: Since 2012-04-20 this holds the change rate %"

    severity = models.IntegerField(choices=SEVERITY_TYPES, default=utils.SEVERITY_UNKNOWN)
#    severity.help_text = "NB: Since 2012-04-20 this is READ-ONLY and based on change rate %"

    status = models.IntegerField(choices=ADVISORY_STATUSES, default=STATUS_NEW, db_index=True)
    assigned_to = models.CharField(blank=True, null=True, max_length=64)

    # when information in DB was generated
    last_updated = models.DateTimeField(null=True, blank=True, db_index=True)

    has_static_page = models.BooleanField(default=False, db_index=True)
    overriden = models.BooleanField(default=False, db_index=True)

    def __unicode__(self):
        return unicode("%s to %s" % (self.old, self.new))

    @classmethod
    def get_full_path_from_string(cls, name, old, new, pk):
        """
            Used internally to avoid DB hits.
        """
        return '%s/%s/%s-%s/%s-%s/%d/' % (FQDN, URL_ADVISORIES, name, old, name, new, pk)

    def get_path(self):
        return '/%s/%s/%s/%d/' % (URL_ADVISORIES, self.old, self.new, self.id)

    def get_full_path(self):
        return FQDN + self.get_path()

    def get_title(self): # FALSE NEGATIVE, used in templates
        return "Changes between %s and %s" % (self.old, self.new)

    def severity_img(self): # FALSE NEGATIVE used in templates
        """
            Return the HTML img tag with icon representing Severity
        """
        sev_display = self.get_severity_display()
        return "<img src='%si/s/%s.png' alt='%s' title='%s' />" % (STATIC_URL, self.severity, sev_display, sev_display)



class ApplicationHistory(models.Model):
    """
        Records package history as text.
    """

    # override default QuerySet manager
    objects = SkinnyManager()

    application = models.ForeignKey(Application, unique=False)
    when_added = models.DateTimeField(db_index=True)
    packages = models.TextField(null=True, blank=True)
    comments = models.CharField(max_length=256, null=True, blank=True)

    def __unicode__(self):
        return unicode("%s - %s" % (self.application.name, self.when_added))

class Bug(models.Model):
    """
        Holds bugs description.
    """

    # override default QuerySet manager
    objects = SkinnyManager()

    advisory = models.ForeignKey(Advisory, unique=False)
    number = models.IntegerField(db_index=True) # for bugs dedup maybe ???
    title = models.CharField(max_length=256, null=True, blank=True)
    url = models.URLField()
    context = models.CharField(max_length=256, null=True, blank=True)
    reported_on = models.DateTimeField(db_index=True, null=True, blank=True, default=None) # indexes for future queries
    closed_on = models.DateTimeField(db_index=True, null=True, blank=True, default=None)

    def __unicode__(self):
        return unicode("%s - %d: %s" % (self.url, self.number, self.title))


class MockProfile(models.Model):
    """
        Any user profile class should inherit from this
        and override any default methods.
    """

    objects = SkinnyManager()

    user = models.ForeignKey(User, unique=True)

    def get_email_delay(self):
        return 1 # notify every day

    def is_subscribed(self):
        return True

    def get_subscription_plan_name(self):
        return "Beaker"

    class Meta:
        abstract = True
