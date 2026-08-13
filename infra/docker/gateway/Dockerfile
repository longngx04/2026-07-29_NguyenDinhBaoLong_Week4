FROM nginx:1.27-alpine
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/00-limits.conf
EXPOSE 8080
