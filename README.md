# letsexpose
A simple framework to expose you linux http services as https using [Let's Encrypt](https://letsencrypt.org/) certificates and [nginx](https://www.nginx.com/) running in a [docker](https://www.docker.com/) container.
## How to use
 - Make sure you have you backend services running on the local host listening to some ports
 - Make sure your firewall rules are set to allow incoming external HTTP and HTTPS traffic to the host.
 - Clone this repository or download its contents to a suitable directory. (How about `/opt/letsexpose`?)
 - Copy `config/config.sample.yaml` to `config/config.yaml` and edit the file to suit your needs. The sample file has plenty of comments. Don't forget to use your own e-mail address and set `staging` to `false`!
 - Run `sudo install.sh` and follow the instructions. This script will ask for confirmation before each step!
##  How does it work?
An *nginx* container running under *docker compose* does two things:
 - A server on port 80 handles
	 - challenge requests from *Let's encrypt*
	 - other http requests by redirecting them on to the corresponding https URLs.
 - Server(s) running HTTPS to reverse proxy into local services

Protecting services with single user basic http auth is also supported.

Note that the *nginx* container runs using "[host networking](https://docs.docker.com/network/host/)" in order to access the local services.
## Credits
The *letsexpose framwork* was written by David Björkevik under funding by [Envista](https://www.envista.se/). It more or less implements the method described in [this medium.com article](https://pentacent.medium.com/nginx-and-lets-encrypt-with-docker-in-less-than-5-minutes-b4b8a60d3a71) by [user Philipp](https://pentacent.medium.com/).
