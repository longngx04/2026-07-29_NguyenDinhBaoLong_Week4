FROM nginx:1.27-alpine
COPY docker-entrypoint.d/ /docker-entrypoint.d/
RUN chmod 0755 /docker-entrypoint.d/00-require-key.sh /docker-entrypoint.d/16-acquire-dast-session.envsh
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/00-limits.conf
EXPOSE 8080 8081
