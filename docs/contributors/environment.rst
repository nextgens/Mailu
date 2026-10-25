Development environment
=======================

Git
---

Before any partaking in development, you will need to fork the Mailu repository on GitHub.
For this you will need a `GitHub`_ account. GitHub has excellent documentation on:

#. How to `fork a repo`_ and set upstream (Mailu);
#. Keeping your fork `synced`_;
#. Sending a `pull request`_.

Working on Mailu usually requires you to clone (download) your fork to your work station and
create a branch. From here you can work on Mailu. When done, create a commit and push the
branch to your GitHub repository. Then, on GitHub you can create a "pull request".
Please make sure you have read the :ref:`git_workflow` section of the *Development guidelines*
before submitting any pull requests.

.. note:: It is strongly advised to **never** modify the ``master`` branch of your fork.
  This will make it impossible to sync your fork with upstream and creating new (and clean)
  branches! This includes never merging other branches from yourself or other users into your
  ``master``. If you want to do that, create a separate branch for it.

Short work flow example
```````````````````````

.. code-block:: bash

  git clone https://github.com/<YOUR_USERNAME>/Mailu.git
  cd Mailu
  git remote add upstream https://github.com/Mailu/Mailu.git
  git checkout -b fix-something master

Work on the code as desired. Before doing a commit, you should at least build
and run the containers. Keep reading this guide for more information. After this,
continue to commit and send a PR.

.. code-block:: bash

  git commit -a
  #Enter commit message in editor, save and close.
  git push --set-upstream origin fix-something

Now you can go to your GitHub page, select the new branch and "send pull request".

Updating your fork
``````````````````

The Mailu ``master`` branch is an ever evolving target. It is important that newly
created branches originate from the latest ``upstream/master``. In order to do so, you will
need to `sync your fork`__:

.. code-block:: bash

  git fetch --all
  git checkout master
  git merge upstream/master

If you kept your master branch clean, this should fast-forward it to the latest upstream version.
Likewise, if you worked on your branch for a longer amount of time, it is advised to merge the
latest ``upstream/master`` into the branch.

.. code-block:: bash

  git checkout my-old-branch
  git merge upstream/master

Now, git won't fast forward but write a merge commit. Typically you can accept the commit message
presented. Read the output if there are any merge conflicts. In ``git status`` you can find the files
that need editing to have the desired contents. Also, it will tell you how to mark them as resolved.

Optionally, you can ``git push`` after any of above merges to propagate them to GitHub.

__ `synced`_

Bad habits
```````````

Some bad habits from users that we are sometimes confronted with. Please refrain yourself from:

- ``git reset REF`` and ``git push --force`` after submitting a PR.
- Merge a branch (other then master) into yours and submitting a PR before that other branch got
  merged into master. It will cause you to submit commits someone else wrote and are probably outside
  the subject of your PR. (There are valid cases however, but take care!)
- ``git reset REF`` after merging ``upstream/master`` into your branch. It will unstage **all**
  changed files that where updated in the merge. Your will have to clean up all of them
  (don't delete!) using ``git checkout -- <file>``. And take care not to do that to the files you
  have modified. However, it can be that the merge modified some other lines then yours. You'll have
  to make sure there will be no conflicts when you are submitting this messed up branch to Mailu! You
  get the point, I hope.
- ``git rebase`` on a branch that is pull-requested. Others will not be able to see you modified the
  branch and it messes with the order of commits, compared to a merge. It might break things after we
  have conducted tests.

.. _`GitHub`: https://github.com/
.. _`fork a repo`: https://help.github.com/articles/fork-a-repo/
.. _`synced`: https://help.github.com/articles/syncing-a-fork/
.. _`pull request`: https://help.github.com/articles/about-pull-requests/

Docker containers
-----------------

The development environment is quite similar to the production one.

Building images
```````````````

We supply a separate ``test/build.hcl`` file for convenience.
After cloning the git repository to your workstation, you can build the images:

.. code-block:: bash

  cd Mailu
  docker buildx bake -f tests/build.hcl --load

The ``build.hcl`` file has three variables:

#. ``$DOCKER_ORG``: First part of the image tag. Defaults to *ghcr.io/mailu* and needs to be changed
   only  when pushing to your own Docker hub account.
#. ``$MAILU_VERSION``: Last part of the image tag. Defaults to *local* to differentiate from pulled
   images.
#. ``$MAILU_PINNED_VERSION``: Last part of the image tag for x.y.z images. Defaults to *local* to differentiate from pulled
   images.


To re-build only specific containers at a later time.

.. code-block:: bash

  docker buildx bake -f tests/build.hcl admin webdav

If you have to push the images to Docker Hub for testing, you have to
define ``DOCKER_ORG`` (usually your Docker user-name) and login to
the hub.

.. code-block:: bash

  docker login
  Username: Foo
  Password: Bar
  export DOCKER_ORG="Foo"
  export MAILU_VERSION="feat-extra-app"
  export MAILU_PINNED_VERSION="feat-extra-app"
  docker buildx bake -f tests/build.hcl --push

Running containers
``````````````````

To run the newly created images: ``cd`` to your project directory. Edit ``.env`` to set
``VERSION`` to the same value as used during the build (for MAILU_VERSION), which defaults to ``local``.
After that you can run:

.. code-block:: bash

  docker compose up -d

If you wish to run commands inside a container, simply run (example):

.. code-block:: bash

  docker compose exec admin ls -lah /

Or if you wish to start a shell for debugging:

.. code-block:: bash

  docker compose exec admin sh

Finally, if you need to install packages inside the containers for debugging:

.. code-block:: bash

  docker compose exec admin apk add --no-cache package-name

Reviewing
---------

Members of the **Mailu/contributors** team leave reviews on open PR's.
In the case of a PR from a fellow team member, a single review is enough
to initiate merging. In all other cases, two approving reviews are required.
There is also a possibility to set the ``review/need2`` to require a second review.

Mergify has separate integration queues for ``master`` and ``2024.06``. It tests batches of up to five
pull requests together with the latest version of the target branch before fast-forwarding a successful batch.
A pull request needs the required approvals and a successful ``CI-Done`` check before it can merge. The approval policy
is one review for trusted authors, unless ``review/need2`` is set, and two reviews for everyone else.

Pull requests from authors GitHub identifies as ``OWNER``, ``MEMBER``, ``COLLABORATOR`` or
``CONTRIBUTOR`` are queued automatically for CI. For other authors, a reviewer can request the same
queue test by adding the ``queue-for-ci`` label. This only starts testing; the regular review count
is still required to merge. The Mergify queue command remains restricted to administrators so that
reviewers cannot select the review-bypass queue.

The merge queue creates a temporary draft pull request for each batch. Its GitHub Actions run builds and
tests the combined changes and publishes test images to the GitHub Container Registry. To test an image,
find the active draft pull request whose title begins with ``merge queue:`` and use its PR number:

.. code-block:: bash

  export DOCKER_ORG="ghcr.io/mailu"
  export MAILU_VERSION="pr-<queue-pr-number>-build"
  docker compose pull
  docker compose up -d

When a batch changes, Mergify rebuilds it. WIP pull requests and those with the ``status/wip`` or
``status/blocked`` label stay out of the queue. Additional commits dismiss previous approvals, as before.

Administrators can bypass the review count for an exceptional merge by commenting:

.. code-block:: text

  @mergifyio queue admin-override

For a pull request targeting ``2024.06``, use:

.. code-block:: text

  @mergifyio queue admin-override-2024.06

The admin-only queue still requires the ``CI-Done`` check and still excludes WIP and blocked pull requests.

System requirements
```````````````````

Reviewing pull requests sometimes requires some additional git setup. First, for 90% of the review jobs,
you will need a PC or server that can expose all Mailu ports to the outside world. Also, a valid
domain name would be required. This can be a simple free DynDNS account. Do not use a production
server, as there are cases where data corruption occurs and you need to delete the ``/mailu``
directory structure.

.. _testing:

Test images
```````````

Reviewers can test the images from the active Mergify queue batch as described above. Play around. See if
(external) mails work. Check whatever functionality the PR is trying to fix. When happy, approve the original
pull request. When running into failures, mark the review as "request changes" and provide as many details
as possible (logs, error codes from clients, etc.).

Additional commits
``````````````````

On every new commit, Mergify rebuilds the active queue batch. Past approvals are dismissed automatically.
When doing a subsequent review on the same PR, be sure to pull the latest queue image before testing again.

When queue checks fail
````````````````````````

If queue checks fail, inspect the GitHub Actions run linked from the temporary draft pull request. Fixing the
source pull request updates the batch and starts a fresh run.

Reviewing by git
----------------

Sometimes it might not be possible or enough to pull the test images from Docker hub.
In those cases, it will be necessary to do a local git merge and perhaps manually building
of the relevant images.


Preparations
````````````

#. Setup `Git`_ the same way as on a development PC. It is advised to keep ``origin`` as your
   own repository and ``upstream`` as the one from Mailu. This will avoid confusion;
#. You will need a ``docker-compose.yml`` and ``.env``, set up for the test server;
#. Make sure that the build ``$VERSION`` corresponds with those files.

Add the sender
``````````````

Replace ``<SENDER>`` with the repository name the PR is sent from.

.. code-block:: bash

  git remote add <SENDER> https://github.com/<SENDER>/Mailu.git

Merge conflicts
```````````````

Before proceeding, check the PR page in the bottom. It should not indicate a merge conflict.
If there are merge conflicts, you have 2 options:

#. Do a review "request changes" and ask the author to resolve the merge conflict.
#. Solve the merge conflict yourself on Github, using the web editor.

If it can't be done in the web editor, go for option 1. Unless you want to go through the trouble of
importing the branch into your fork, do the merge and send a PR to the repository of the *sender*.

Merge the PR locally
```````````````````````

When someone sends a PR, you need merge their PR into master locally. This example will put you in a
"detached head" state and do the merge in that state. Any commits done in this state will be lost
forever when you checkout a "normal" branch. This is exactly what we want, as we do not want to mess
with our repositories. This is just a test run.

The following must be done on every PR or after every new commit to an existing PR:
1. Fetch the latest status of all the remotes.
2. List all local and remote available branches (this is not needed, but very helpful at times)
3. Checkout ``upstream/master``
4. Merge ``upstream/master`` with ``SENDER/branch``

.. code-block:: bash

  git fetch --all
  git checkout upstream/master
  # ...You are in 'detached HEAD' state.... (bla bla bla)
  git branch -a
  # Hit `q` to exit the viewer, if it was opened. Uses arrows up/down for scrolling.
  git merge kaiyou/fix-sender-checks

If git opens a editor for a commit message just save and exit as-is. If you have a merge conflict,
see above and do the complete procedure from ``git fetch`` onward again.


Web administration development
------------------------------

The administration web interface requires a proper dev environment that can easily
be setup using the ``run_dev.sh`` shell script. You need ``docker`` or ``podman``
to run it. It will create a local webserver listening at port 8080:

.. code-block:: bash

  cd core/admin
  ./run_dev.sh
  pip install -r requirements.txt
  [...]
  =============================================================================
  The "mailu-dev" container was built using this configuration:

  DEV_NAME="mailu-dev"
  DEV_DB=""
  DEV_PROFILER="false"
  DEV_LISTEN="127.0.0.1:8080"
  DEV_ADMIN="admin@example.com"
  DEV_PASSWORD="letmein"
  =============================================================================
  [...]
  =============================================================================
  The Mailu UI can be found here: http://127.0.0.1:8080/sso/login
  You can log in with user admin@example.com and password letmein
  =============================================================================

The container will use an empty database and a default user/password unless you
specify a database file to use by setting ``$DEV_DB``.

.. code-block:: bash

  DEV_DB="/path/to/dev.db" ./run_dev.sh

Any change to the files will automatically restart the Web server and reload the files.

When using the development environment, a debugging toolbar is displayed on the right
side of the screen, where you can access query details, internal variables, etc.


Documentation
-------------

Documentation is maintained in the ``docs`` directory and are maintained as `reStructuredText`_
files. It is possible to run a local documentation server for reviewing purposes, using Docker:

.. code-block:: bash

  cd <Mailu repo>
  docker build -t docs docs
  docker run -p 127.0.0.1:8080:80 docs

In a local build Docker always assumes the version to be master.
You can read the local documentation by navigating to http://localhost:8080/master.

.. note:: After modifying the documentation, the image needs to be rebuild and the container
  restarted for the changes to become visible.

.. _`reStructuredText`: http://docutils.sourceforge.net/rst.html
