FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG REACT_APP_HOBIT_BACKEND_ENDPOINT=http://localhost:8000
ENV REACT_APP_HOBIT_BACKEND_ENDPOINT=$REACT_APP_HOBIT_BACKEND_ENDPOINT
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
