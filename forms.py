################################################################################
#
#   Copyright (c) 2012-2013, Alexander Todorov <atodorov@nospam.dif.io>
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


from django import forms

class PipFreezeForm(forms.Form):
    """
        Python - allows the user to import `pip freeze` output.
    """
    pipfreeze = forms.CharField(widget=forms.Textarea, initial="")
    pipfreeze.help_text = "Paste the output of the <strong>pip freeze</strong> command below"

class BundleListForm(forms.Form):
    """
        Ruby - allows the user to import `bundle list` output.
    """
    bundlelist = forms.CharField(widget=forms.Textarea, initial="")
    bundlelist.help_text = "Paste the output of the <strong>bundle list</strong> or <strong>gem list</strong> commands below"

class NpmLsForm(forms.Form):
    """
        Node.js - allows the user to import `npm ls` output.
    """
    npmls = forms.CharField(widget=forms.Textarea, initial="")
    npmls.help_text = "Paste the output of the <strong>npm ls</strong> command below"

class PerlLocalForm(forms.Form):
    """
        Perl - allows the user to import the perllocal.pod file.
    """
    perllocal = forms.FileField()
    perllocal.help_text = "Upload <strong>perllocal.pod</strong>, which contains a list of installed distributions"

class MvnDependencyListForm(forms.Form):
    """
        Java / Maven Central - allows the user to import `mvn dependency:list` output.
    """
    mvn = forms.CharField(widget=forms.Textarea, initial="")
    mvn.help_text = """
<strong>Use this form to import Java packages from Maven Central</strong><br /><br />
Paste the dependency list section of the <strong>mvn dependency:list</strong> command below
"""

class ComposerShowForm(forms.Form):
    """
        PHP / Composer - allows the user to import `./composer.phar show -i` output.
    """
    composer = forms.CharField(widget=forms.Textarea, initial="")
    composer.help_text = """
<strong>Use this form to import PHP packages from Packagist.org</strong><br /><br />
Paste the output of <strong>php composer.phar show --installed</strong> command below
"""


class InviteFriendsViaMailForm(forms.Form):
    """
        Send invitation email to friends.
    """
    recipients = forms.CharField(widget=forms.TextInput, initial="")
