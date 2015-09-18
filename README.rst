Castor
======

Provides a way to assemble various Git repositories into one. It's like submodules that don't suck.

Use case: stitch together Wordpress with some themes and plugins before deploying.

Usage
~~~~~

First, you need to create your Castor repository. The following command will create an new Git
repository containing an empty ``Castorfile`` and a pre-initialized .gitignore.

.. code-block::

   castor init my-proj

Then, you need to edit your ``Castorfile``. It might look like

Note
++++

``post_freeze`` array is optional. It must be an array, each command will be executed
on the ``target`` directory after executing ``castor freeze``.

.. code-block::

   {
       "lodge": [
           {
               "target": "/",
               "version": "1.6.1.0",
               "repo": "https://github.com/PrestaShop/PrestaShop.git",
               "type": "git"
           },
           {
               "target": "/themes/my-prestashop-theme",
               "version": "e0e7c15789e6ff674cd75cb24981155441c3df09",
               "repo": "git@bitbucket.org:activkonnect/my-prestashop-theme.git",
               "type": "git",
               "post_freeze": [
                   "composer update --no-dev"
               ]
           },
           {
               "target": "/.htaccess",
               "type": "file",
               "source": "files/htaccess"
           }
       ]
   }

Your ``Castorfile`` being filled up, you can now apply it

.. code-block::

   castor apply

This will automatically create your repositories hierarchy, checkout submodules, etc. The root of
this hierarchy will be the ``lodge`` directory.

Now you can freeze your project into a git-free, commitable and deployable tree of source code.
This will go into the ``dam`` directory.

.. code-block::

   castor freeze

You can use the ``lodge`` as your working directory during development. If you make updates to the
code, you can commit in the git repos. If you simply want to update upstream code, check out the new
tag/commit you want to use. Then  you can use ``castor freeze`` again, and it will update the
``Castorfile`` automatically with the latest Git HEADs, as well as the ``dam`` directory.


