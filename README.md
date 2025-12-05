# About

**Signatories** is a simple web-based program that allows a person to sign
an online petition, a declaration, a statement, or any form of communication
that requires community support. Designed for academics, signing is accomplished
by authenticating with an account at [ORCID](https://orcid.org).

Campaigns can choose to allow for anonymous signatures or not. Signatories
to a campaign may choose to add their professional affiliation, and they can
modify their preferences or remove their signature after signing. When the
signatory's name is visible, any user may click on it to inspect their ORCID
profile.

By requiring an account at ORCID to sign, not only are bogus signatures
avoided, but this helps to limit participants to the academic community. An
ORCID account may sign at most once, and anonymous participants are assured to
have an ORCID account.

Administrators can assign users as editors.
Editors can create campaigns, or modify, delete or close campaigns for which they
are the owner.

This code is based on the Planetary Research
[Reviewer expertise database](https://review.planetary-research.org), which is
in turn based on the [Seismica](https://seismica.library.mcgill.ca/) reviewer
expertise database that was created originally by
[Martijn van den Ende](https://github.com/martijnende).

# Dependencies

```
conda create -n signatories python=3.13 python-dotenv flask flask-sqlalchemy sqlalchemy-utils orcid waitress -c conda-forge
```

# Instructions

## Initial setup

When running in production, place the project files in an appropriate directory
such as `/var/www/signatories`. For testing, any directory will do.

Copy the file `.env.sample` to `.env`, which should look like the following:

```txt
cookie_secret = '...'  # Random string to cross-check the stored cookie. Any string will do.
port = 3000

# Orcid ID of the site admin that is added to the database at creation
admin_orcid = 'xxxx-xxxx-xxxx-xxxx'

# Set favicon (use "" for none). File name is with respect to static/img
favicon = "favicon.ico"

# URL and name of a link displayed in the website footer, such as the association website
footer_url_name = "My-Organization"
footer_url = "https://my.organization.example.org/"

# Add a statement in the footer that states Signatories was created by the Planetary Research Cooperative
thank_prc = false

# Contact email in the footer
contact_email = "tech@my-organization.example.org"

# ORCID API credentials
client_ID = 'APP-ABCDEFGHIJKLMNOP'
client_secret = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'

# If the ORCID client credentials correspond to a member account, set to 1
orcid_member = 0

# Uncomment and provide a public URL when used in production. When public_domain
# is not set, the app will use the ORCID sandbox API.
# public_domain = 'https://signatories.example.org'
```

Then modify the following variables:

1. `cookie_secret`: a random string to cross-check the stored cookie. Any string will do.
2. `client_ID`, `client_secret`: ORCID API credentials.

> For testing, register for a [sandbox ORCID API](https://sandbox.orcid.org/) using a dummy email address. When the API is enabled, go to [`ORCID profile > developer tools`](https://sandbox.orcid.org/developer-tools) and create a client ID and secret.
> In production use the main [ORCID API credentials](https://orcid.org/developer-tools).

3. Add a public domain if the application is used in production (not required for local development in sandbox mode).
4. Update the parameters `favicon`, `footer_url_name`, `footer_url`, `thank_prc`, and `contact_email`.

Finally, to run the app, use:
```bash
python app.py
```

## System service

To have the application start automatically when the system reboots, create a file `/etc/systemd/system/signatories.service` with the following contents:

```
[Unit]
Description=Signatories daemon
After=multi-user.target

[Service]
ExecStart=/opt/miniforge3/envs/signatories/bin/python /var/www/signatories/app.py &
Type=simple
Restart=always

[Install]
WantedBy=multi-user.target
```

and then run the following at the command line
```
systemctl daemon-reload
systemctl enable signatories
service signatories start
```

## Reverse proxy

Running the application will enable an http web server on port 3000. To use this
securely with an apache web server, it will be necessary to create a reverse proxy.
First, create the file `/etc/apache2/sites-available/signatories.conf` with
the following:

```
<VirtualHost *:80>
    ServerName signatories.example.org
    Redirect / https://signatories.example.org
</VirtualHost>

<VirtualHost *:443>
    ServerName signatories.example.org
    ProxyPass / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/
    ProxyRequests Off
</VirtualHost>

<Directory /var/www/signatories>
    Options +FollowSymLinks
    Options -Indexes
    AllowOverride All
    order allow,deny
    allow from all
</Directory>
```

Then execute the following commands:
```
a2enmod proxy
a2enmod proxy_http
systemctl restart apache2
a2ensite signatories.conf
```

## Notes

* The database is by default located at `db/signatories.db`.
* If you change from sandbox to production modes (by setting `public_domain`), you should re-initialize the database. Otherwise sandbox accounts will appear in the production database.
