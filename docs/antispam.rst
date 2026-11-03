Spam filtering
==============

.. _antispam_howto:

How does spam filtering work in Mailu?
--------------------------------------

Mailu uses Rspamd for spam filtering. Rspamd is a Fast, free and open-source spam filtering system.

Rspamd rejects non-compliant email messages and email messages that contain viruses. It adds up scores from its checks and compares the result with configured action thresholds. Mailu's default thresholds can be changed inside the Rspamd WebUI under the configuration tab:

* Email messages with a score of 8 or higher will be rejected.

* Email messages with a score of 6 or higher will receive a header with the spam score.

* Email messages with a score of 4 or higher will be greylisted.

* Email messages with a score of 3 or lower will be accepted.

Quarantine and greylist copies are stored under ``/data/quarantine`` in
two-character shard directories. New records use a BLAKE2s hash of the
Message-ID, with separate namespaces for quarantine and greylisting. The first
ten bits select the directory, encoded in lowercase base32. A generated ID is
used when the Message-ID is missing or invalid, and for additional quarantined
messages with the same ID. Such greylisted messages cannot be matched to a
later retry and remain until deleted or expired. On the first start after upgrading, existing flat records are moved into
shards before the admin service starts; old greylist IDs are recalculated, so
links to those IDs change. The migration resumes if interrupted and startup
fails if it encounters conflicting files. Stop older admin instances before
the upgrade, and include the entire repository in backups.

Rejected messages are retained in the quarantine for 90 days. Administrators can
view all quarantined messages, while mailbox users can view messages addressed
to them. Release submits the original message to Postfix through an internal
reinjection listener, bypassing the original Rspamd decision while preserving
normal mailbox, alias, forwarding, and relay routing. A bounded text preview
is escaped before display; attachments are not rendered in the quarantine view.

Rspamd's rejection thresholds remain configurable in the Rspamd WebUI. Lowering
the spam rejection threshold causes more high-scoring messages to be quarantined
instead of being accepted for delivery.

1. When an email message is received or sent by Postfix, it is scanned by Rspamd. If it receives a spam score of 6 or higher and is not rejected, Rspamd adds spam headers. This is an example of an email header for a spam score of 7::

    X-Spamd-Bar: +++++++
    X-Spam-Level: *******
    Authentication-Results: test.mailu.io;
       dkim=pass header.d=example.com header.s=mailing header.b=ABCDE;
       dkim=pass header.d=example.com header.s=mailing header.b=ABCDE;
       dmarc=pass (policy=none) header.from=eventim.de;
       spf=pass (test.mailu.io: domain of return@example.com designates 11.22.33.44 as permitted sender) smtp.mailfrom=return@example.com
    X-Spam: Yes

2. Dovecot is then responsible for classifying the email message to the Junk folder based on user preferences. It works as following:

   * In the administration web interface, under settings under Antispam 'Enable spam filter' must be ticked. If this option is disabled, then all delivered email messages will automatically go to the inbox folder. Messages with a score of 8 or higher are rejected by Rspamd before delivery.

   * In the administration web interface, under settings under Antispam, the user defined spam filter tolerance must be configured. The default value is 80%. The lower the spam filter tolerance, the more false positives (ham classified as spam). The user can change this setting to fine-tune when an email message is classified as spam.

   * Dovecot extracts the X-Spam-Level email header and maps its value using a maximum score of 15 to a 0 - 100 percent scale. This delivery-time spam score is compared with the user defined spam filter tolerance. The maximum of 15 is independent of Rspamd's reject threshold. If the spam score is lower than the user defined spam filter tolerance, then the email message is accepted. In logic:

     If <spam_score in percent> is greater than <spam filter tolerance>, then move the email message to the spam folder and mark the email message as read.

   For example, if the user defined spam filter tolerance is set to 80% (the default) and a delivered email has a spam score of 7:

   47% (7/15) is less than 80%, so the email is classified as ham and goes to the inbox. To classify a delivered score of 7 as spam, lower the user defined spam filter tolerance below 47% in the administration web interface.

   The default spam filter tolerance used for new users can be configured using the environment variable ``DEFAULT_SPAM_THRESHOLD``. See also :ref:`common_cfg` in the configuration reference.

.. image:: assets/screenshots/SpamFiltering.png

The location in the administration web interface where the spam filter and spam filter tolerance can be configured.

*Issue reference:* `1167`_.

Can I learn ham/spam messages from an already existing mailbox?
---------------------------------------------------------------

Mailu supports automatic spam learning for email messages delivered or moved to the Junk Folder. Any email messages delivered to or moved to the Junk Folder will be re-learned as spam. Messages copied or delivered from the Junk Folder to any other folder (but the trash folder) will be re-learned as ham.

If you already have an existing mailbox and want Mailu to learn them all as ham messages, you might run rspamc from within the dovecot container:

.. code-block:: bash

  rspamc -h antispam:11334 -P mailu -f 13 fuzzy_add /mail/user\@example.com/.Ham_Learn/cur/
  rspamc -h antispam:11334 -P mailu learn_ham /mail/user\@example.com/.Ham_Learn/cur/

This should learn every file located in the ``Ham_Learn`` folder from user@example.com

Likewise, to learn all messages within the folder ``Spam_Learn`` as spam messages :

.. code-block:: bash

  rspamc -h antispam:11334 -P mailu -f 11 fuzzy_add /mail/user\@example.com/.Spam_Learn/cur/
  rspamc -h antispam:11334 -P mailu learn_spam /mail/user\@example.com/.Spam_Learn/cur/

*Issue reference:* `1438`_.

Experimental bilingual FastText neural classifier
--------------------------------------------------

The experimental Rspamd profile uses the standard Alpine Rspamd package and
content embeddings only. It applies the 32-dimensional English and French
models to every message (``multi_model = true``), then uses mean/max pooling.
The input has 128 values per message: 2 languages x 32 dimensions x 2 pools.
Rspamd symbols and metatokens are explicitly excluded with
``disable_symbols_input = true`` and ``fusion.include_meta = false``. No symbol
whitelist is required for this profile. ``NEURAL_FASTTEXT_SPAM`` has weight
``+1.0`` and ``NEURAL_FASTTEXT_HAM`` has weight ``-1.0``, so a ham prediction
reduces the score while a spam prediction raises it. These experimental weights
are intentionally small; validate their impact against local traffic before
changing action thresholds.

The tested English and French models occupy 127.1 MiB and 128.7 MiB on disk.
On the ARM64 Rspamd 4.0.1 test stack their mapped PSS was 127.1 MiB and
128.7 MiB in the process that handled scans. The latest balanced test ANN
payload was 39,598 bytes compressed. This test used 32-dimensional models
because the standard Mailu Rspamd package has no BLAS support for
``max_inputs``/PCA; no Rspamd source was compiled or patched.

The Dovecot Junk-folder learning scripts now make an additional normal Rspamd
scan carrying the ``ANN-Train`` HTTP header, alongside the existing
``learn_spam`` / ``learn_ham`` commands. This gives the neural module an
explicit correction label while keeping the existing Bayes and fuzzy learning
operations. Rspamd handles this label on scan requests; the header is not
attached to the special Bayes learn endpoint. See the `neural module documentation
<https://docs.rspamd.com/modules/neural/>`_.

Image and deployment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The experimental images are published for AMD64 and ARM64. The English and
French FastText models are distributed together as a separate OCI artifact so
the large binaries do not enter the Mailu source repository. The Rspamd image
copies both into ``/usr/share/rspamd/fasttext``. The published tags are:

* ``ghcr.io/nextgens/mailu/rspamd:neural-content-en32-fr32``
* ``ghcr.io/nextgens/mailu/dovecot:neural-content-en32-fr32``
* ``ghcr.io/nextgens/mailu/fasttext-en-fr32:en-fr-32d-dsub2``

The Dovecot image carries the updated IMAPSieve learning scripts. Once the
production Compose configuration selects these tags, pull and recreate the two
services from the directory containing the Compose file:

.. code-block:: bash

  docker compose pull antispam imap
  docker compose up -d antispam imap

Keep the existing Redis volume: it holds the neural vectors and trained ANN
across container recreation. The model files are part of the Rspamd image, so
upgrading or rolling back that image also changes the embeddings. The ANN is
keyed by its Rspamd rule/profile and the symbols selected for that profile.
In Rspamd 4.0.1, FastText model paths and ``multi_model`` are not included in
the provider digest. If changing those settings changes the input features,
use a distinct neural rule prefix and train a fresh profile instead of
assuming Rspamd will isolate the old vectors automatically.

Confirm that the Rspamd container is healthy, run
``docker compose exec antispam rspamadm configtest``, and check its logs for
the EN32 and FR32 model loading messages. The network will have no ANN until enough
explicitly labeled vectors have been trained. With the shipped weights, spam
predictions add one point and ham predictions subtract one point. To disable
the neural contribution while investigating it, override both symbol weights
to zero in ``/mailu/overrides/rspamd/metrics.conf`` and restart ``antispam``.

Evaluating on a full ham set
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For a valid false-positive measurement, keep the ham messages being evaluated
out of neural training. Split by message/thread or campaign where possible,
not only by filename. Make a manifest containing one known-ham message path
per line. Paths in the manifest must be visible inside the Dovecot container,
for example ``/mail/user@example.com/cur/message-file``; copy the manifest
into that container, then run a scan (not a learn command):

.. code-block:: bash

  docker compose cp /tmp/ham-files.txt imap:/tmp/ham-files.txt
  docker compose exec -T imap rspamc --json --files-list /tmp/ham-files.txt \
    -h antispam:11334 > ham-scan.jsonl

Count ham as a false positive when its final score meets/exceeds the configured
``required_score`` (or Rspamd returns the configured spam action). Report the
count as well as the rate: one false positive in 302 ham messages is 0.331%,
so this test set cannot establish a 0.1% rate. Save the manifest and scan
output so the same full ham set can be compared against rules-only and neural
configurations. One way to count threshold-crossing messages in the JSONL
output is ``jq -s '[.[] | select(.score >= .required_score)] | length'``.
First scan with the shipped zero weights and save the results. After training,
apply the temporary ±5 ``metrics.conf`` override, rescan the exact same
manifest, and compare scores and actions. A normal ``rspamc`` scan evaluates
the message but does not label it for neural training.

Training and retraining
~~~~~~~~~~~~~~~~~~~~~~~

For initial evaluation, train only on a separate labeled subset, with roughly
balanced spam and ham examples. Then scan the held-out ham manifest above.
With the default ``max_trains = 1000`` and balanced learning, Rspamd starts
training after each class reaches the configured minimum (about 1000 vectors
with the default class bias); training runs asynchronously on the primary
Rspamd controller.
Training vectors are Redis sets, so exact duplicate feature vectors collapse:
balanced message counts do not guarantee balanced vector counts. Check the
``SCARD`` of both class sets as well as the raw message counts. The balanced
mode is an eligibility check; it does not downsample the larger class. Wait for
the ANN profile to appear before measuring. Redis is the authoritative neural
state; back it up and persist it with the normal Mailu Redis volume.

To bulk-train the neural network without changing Bayes, scan balanced labeled
training manifests with the same header used by the IMAPSieve scripts. Do not
use the ``learn_ham`` / ``learn_spam`` command for this initial neural-only
training pass because those commands also update Bayes:

.. code-block:: bash

  docker compose cp /tmp/ham-train-files.txt imap:/tmp/ham-train-files.txt
  docker compose cp /tmp/spam-train-files.txt imap:/tmp/spam-train-files.txt
  docker compose exec -T imap rspamc -h antispam:11334 -P mailu \
    --header='ANN-Train: ham' --files-list /tmp/ham-train-files.txt
  docker compose exec -T imap rspamc -h antispam:11334 -P mailu \
    --header='ANN-Train: spam' --files-list /tmp/spam-train-files.txt

The initial lists should be approximately balanced and exclude the ham set
being evaluated. The network starts training after at least 25 vectors from
each class; the controller trains asynchronously. Check Rspamd logs and Redis
set counts, and wait for the ANN profile before scanning the held-out set.
Automatic training is enabled: Rspamd may also collect vectors from messages
that receive a spam/junk or ham verdict. The explicit Dovecot ``ANN-Train``
labels continue to capture user corrections.
Redis distinguishes a neural *profile index* from the individual ANN model
versions stored in that index. The newest entry in the configured profile is
the model used for inference; older version keys are not additional models
that each message is evaluated against. Inspect profile indexes and the
versions in this rule's index with:

.. code-block:: bash

  docker compose exec -T redis redis-cli --scan --pattern '*NEURAL*'
  docker compose exec -T redis redis-cli --raw ZREVRANGE rn3_NEURAL_FASTTEXT_3_default 0 -1

The profile index name can vary with the Rspamd rule and plugin version. Check
the returned JSON ``redis_key`` to identify its newest model, and use
``SCARD`` on the corresponding ``_ham_set`` and ``_spam_set`` keys to inspect
training counts. Do not interpret older model versions as other profiles or
delete Redis keys by a broad pattern. After training completes, restart
``antispam`` once before held-out scans so the controller reloads the
persisted ANN provider digest; scanning immediately in the process that
trained the model can temporarily produce no neural symbols.
Manual ``ANN-Train`` labels are explicit operator labels and bypass the normal
automatic vector-admission limits. The model still needs the configured
minimum from both classes, and duplicate vectors still collapse in Redis, so
do not scan a large, unbalanced ham archive with that header. The updated Dovecot scripts send both the existing
``learn_ham`` / ``learn_spam`` request and a separate normal scan with an
``ANN-Train`` label, so live user corrections continue to update Bayes and
also train the neural classifier. Keep a backup of Redis
before bulk learning. Training vectors and the trained ANN are stored in
Redis; persist and back up that volume with the normal Mailu state. Do not
delete Redis keys by pattern to force retraining. To compare against a fresh
model, use a separate Redis instance/volume and train it with a selected
balanced training set.

Troubleshooting mixed feature dimensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The neural trainer expects every stored vector in a profile to have the same
length. A training failure in ``compute_zscore_stats`` with
``attempt to perform arithmetic on a nil value`` can indicate that vectors
with different feature layouts were mixed. It is not, by itself, evidence of
score saturation. Inspect the effective rule with
``rspamadm configdump neural`` and confirm that the FastText provider and
intended fusion settings are present. Then inspect the dimensions of the
stored vectors for both classes before retrying.

Rspamd's ``override.d`` has higher priority than ``local.d`` and replaces the
matching rule. A temporary override containing only
``rules.NEURAL_FASTTEXT.train.store_set_only`` can therefore remove the
provider and fusion configuration while collecting examples. In the test
stack this produced 128-value embedding vectors alongside 602-value
symbol-only vectors, and training failed during z-score normalization. When
temporarily freezing training, preserve the complete rule in the override and
change only ``store_set_only``. Run ``rspamadm configtest`` and inspect
``rspamadm configdump neural`` before importing messages. If incompatible
vectors are already stored, keep the trained ANN untouched, remove only the
verified incompatible training sets for the active profile, then recollect a
balanced batch under one unchanged configuration.

With the complete rule preserved, the test stack collected 235 unique vectors
per class (from 250 labeled messages per class); all 470 vectors had 128
features and Rspamd trained a new ANN version successfully. The difference
between message counts and vector counts is expected because Redis sets
deduplicate identical feature vectors. This is a test result, not a
production false-positive or accuracy measurement.

The experimental integration does not alter Mailu action thresholds or the
Bayes/fuzzy configuration. Before production use, compare full-ham scan
results with the neural image disabled and enabled, inspect false positives,
and adjust the neural group weights through a Rspamd metrics override only
after reviewing those paired results.

.. _antispam_howto_block:

How can I block emails from a domain?
-------------------------------------

Via the multimap filter it is possible to block emails from a sender domain. See the `official rspamd documentation`_ for more information. A local blacklist that contains the domains to be blocked can be configured via the :ref:`Rspamd overrides folder <override-label>`.

The following steps have to be taken to configure an additional symbol (rule) that uses the multimap filter to block emails from sender domain.

1. In the overrides folder create a configuration file for the multimap filter. This configuration is included by Rspamd in the main multimap configuration file. This means you do not have to use the "multimap {}" element. Files in the ``/mailu/overrides/rspamd/`` folder are mapped to ``/overrides``.
   Create the file ``/mailu/overrides/rspamd/multimap.conf`` with contents:

   .. code-block:: bash

    #override.d/multimap.conf
    #Tip: Each setting must be closed with a semi-colon ';'.
    local_bl_domain {
      type = "from";
      filter = "email:domain";
      map = "/overrides/blacklist.inc";
      score = 14;
      description = "Senders domain part is on the local blacklist";
      group = "local_bl";
      action = "reject";
    }

   Note the "action = "reject";" line. This is a so-called pre-filter. No further filters/rules are processed when a pre-filter is used. If you omit this line, then the configured score will be added to the total score of the email message. Depending on the end-score after processing all rules, a verdict is made. To override this, you can add the action line. When this symbol (rule) is fired, then this action is immediately taken and no further processing occurs. You can use the following actions:

   * discard: drop an email message, but return success for sender (should be used merely in special cases)

   * reject: reject the email message. This enables the actual blocking of mails from the domain.

   * add header: add email header to indicate spam. This always adds the spam score to the email message. Depending on the user defined spam filter tolerance, the email message is moved to the Inbox folder or Junk folder.

   * no action: allow message. The email message will be allowed without a spam score being added in the mail header. This can be used for creating a whitelist filter.

   * soft reject: temporarily delay message (this is used, for instance, to greylist or rate-limit messages)

   To move an email message to the Junk (Spam) folder, a score of 15 can be used in combination with the action "add header".
   The above example configuration will reject all emails send from domains that are listed in '/overrides/blacklist.inc'.


2. In the Rspamd overrides folder create a map that contains the domains to be blocked. You can use # to add comments.
   Create the file /mailu/overrides/rspamd/blacklist.inc with the following contents:

   .. code-block:: bash

     #Blacklisted domains. All emails from these domains are blacklisted and will be rejected.
     #This file is LIVE reloaded by rspamd. Any changes are EFFECTIVE IMMEDIATELY.
     dummy.com

3. Reload Rspamd by stopping the Rspamd container and starting the Rspamd container again. Example for docker compose setup:

   .. code-block:: bash

     docker compose up antispam --force-recreate -d

4. (Optional) Check if the custom symbol is loaded. To access the Rspamd webgui, log in the Mailu administration web interface with a user that is an administrator and go to Antispam. In Rspamd webgui go to tab Symbols. Change the group drop-down box to local_bl. The following additional rule will be listed.

   .. image:: assets/screenshots/RspamdSymbolBlacklist.png

   The symbol is only displayed if the symbol has no pre-filter (action= line) configured. Changes made in this screen are not saved to the configuration file.

5. Check if the map is available. In rspamd webgui go to configuration, a map is available with the path:
   /overrides/blacklist.inc	Senders domain part is on the local blacklist

   .. image:: assets/screenshots/RspamdMapBlacklist.png

   When clicking on this map, you can live-edit the map via the GUI. Please note that only changes made to maps in the ``/overrides`` folder are persistent as changes made interractively though the GUI will be reverted when the Rspamd container is recreated. All changes (whether through the GUI or on the filesystem) are effective immediately.

For more information on using the multimap filter see the official `multimap documentation`_ of Rspamd.

.. _`official rspamd documentation`: http://rspamd.com/doc/modules/multimap.html#from-rcpt-and-header-filters
.. _`multimap documentation`: https://rspamd.com/doc/modules/multimap.html

*Issue reference:* `1566`_.

.. _`1438`: https://github.com/Mailu/Mailu/issues/1438
.. _`1167`: https://github.com/Mailu/Mailu/issues/1167
.. _`1566`: https://github.com/Mailu/Mailu/issues/1566

Can I change the list of authorized file attachments?
-----------------------------------------------------

Mailu rejects emails with file attachments it deems to be "executable" or otherwise dangerous. If you would like to tweak the block list, you can do so using the following commands:

   .. code-block:: bash

     docker compose exec antispam cat /etc/rspamd/local.d/forbidden_file_extension.map > overrides/rspamd/forbidden_file_extension.map
     docker compose restart antispam

Now the file `overrides/rspamd/forbidden_file_extension.map` can be edited, to make changes to the forbidden file extensions list.
For the changes to take effect, rspamd must be restarted.

Mailu rejects emails with documents attached containing some macros. How can I fix it?
--------------------------------------------------------------------------------------

If configured to do so, Mailu uses a lightweight tool called `mraptor from oletools`_ to scan documents containing macros. By default only macros deemed potentially harmful are blocked, but there may be false positives. If you want to change the default behaviour, you may need to override the ``/etc/rspamd/local.d/composites.conf`` file in the antispam container. The following commands may be useful:

   .. code-block:: bash

     docker compose exec antispam cat /etc/rspamd/local.d/composites.conf > overrides/rspamd/composites.conf
     docker compose restart antispam

Now the file `overrides/rspamd/composites.conf` can be edited, to override the mraptor configuration in rspamd.
For the changes to take effect, rspamd must be restarted.

.. _`mraptor from oletools`: https://github.com/decalage2/oletools/wiki/mraptor

Shared spam maps
----------------

Global administrators and domain administrators can manage shared spam lists
from **Administration → Spam settings**. The page supports ARC signer domains,
greylist IP and domain allowlists, URL regular expressions, sender domain
allowlists and denylists, and URL redirector domains. These lists are served
directly to Rspamd as maps and update without restarting the antispam service.

Mailu keeps the configured upstream greylist allowlist feeds enabled and also
loads ``/overrides/greylist-whitelist-domains.inc`` when that file exists. The
upstream Rspamd redirector map is likewise kept alongside locally configured
redirector domains.

Pending greylist retries appear in the main quarantine table with a distinct
highlight. Both rejected and greylisted copies use the same file-backed
repository, with a record kind controlling their lifecycle: rejected messages
are retained for 90 days and pending greylist retries for seven. Mailu
temporarily saves a greylisted copy so an administrator can release it
immediately through Postfix's internal reinjection listener. Rspamd retry scans are
correlated by Message-ID; an accepted retry removes only the pending greylist
record. Since a greylisted message was already temporarily rejected, the sender
may still retry after an administrator releases the saved copy, which can result
in a duplicate delivery.

Releasing a message first submits it to Rspamd's ham learners, then injects it
through a private Postfix SMTP listener. This bypasses a second Rspamd decision
while allowing Postfix to apply the selected envelope recipients' normal alias,
forwarding, mailbox, and relay routing.

The same Spam settings page can enable quarantine summary emails and set a daily,
weekly, or monthly cadence. Each enabled mailbox receives only the quarantined
messages addressed to it. The default English HTML template includes links to
each message; templates are sanitized before delivery and must contain the
``quarantine_table`` placeholder. The Admin job checks hourly and sends a
summary when its selected interval is due. Use **Send me a test** to send the current
template to the signed-in administrator without saving it.
