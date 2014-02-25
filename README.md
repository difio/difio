What is Difio
-------------

"If an application works, any change in its libraries or the versions of those
libraries can break the application." - virtualenv

Difio keeps track of packages and tells you when they change.
It provides multiple change analytics so you can make an informed decision when
or what to upgrade. Difio seeks to minimize the risk of upgrading upstream packages
inside your applications.

Difio is a Django based application. For development queries please head to the
[difio-devel](https://groups.google.com/forum/#!forum/difio-devel) group.


Supported programming languages and package sources
---------------------------------------------------

The following programming languages and package sources are supported:

* Java - http://search.maven.org
* Node.js - https://www.npmjs.org
* Perl - http://search.cpan.org
* PHP - https://packagist.org, http://pear.php.net, http://pear2.php.net
* Python - https://pypi.python.org/pypi
* Ruby - https://rubygems.org


Copyright
---------

Difio was initially developed by [Alexander Todorov](https://github.com/atodorov)
and [Svetlozar Argirov](https://github.com/zaro) for [www.dif.io](http://www.dif.io).

Difio, except where otherwise noted, is released under the
[Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0.html).
See the LICENSE file located in this directory.

How to install
---------------

    $ django-admin.py startproject mysite
    $ cd mysite/
    $ git clone https://github.com/difio/difio
    $ pip install -r difio/requirements.txt

