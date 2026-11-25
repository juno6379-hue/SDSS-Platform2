FROM node:22-alpine AS react
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=react /app/dist /usr/share/nginx/html
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["nginx", "-g", "daemon off;"]
CMD []
