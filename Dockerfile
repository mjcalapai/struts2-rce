# FROM tomcat:7
# MAINTAINER piesecurity <admin@pie-secure.org>
# ENV ADMIN_USER="mark"
# ENV PG_VERSION 9.3.4
# ENV ADMIN_PASSWORD="jigsawroxx"
# RUN set -ex \
# 	&& rm -rf /usr/local/tomcat/webapps/* \
# 	&& chmod a+x /usr/local/tomcat/bin/*.sh
# COPY target/struts2-rest-showcase.war /usr/local/tomcat/webapps/ROOT.war
# EXPOSE 8080

FROM tomcat:7
MAINTAINER piesecurity <admin@pie-secure.org>

ENV ADMIN_USER="mark"
ENV PG_VERSION=9.3.4
ENV ADMIN_PASSWORD="jigsawroxx"

RUN set -ex \
    && printf 'deb http://archive.debian.org/debian buster main\n' > /etc/apt/sources.list \
    && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99archive \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/tomcat/webapps/* \
    && chmod a+x /usr/local/tomcat/bin/*.sh

COPY target/struts2-rest-showcase.war /usr/local/tomcat/webapps/ROOT.war

EXPOSE 8080
