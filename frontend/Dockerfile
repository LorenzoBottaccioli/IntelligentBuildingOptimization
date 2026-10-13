####################################
# Etapa 1: Build con Node (Vite)   #
####################################
FROM node:18-alpine AS builder
WORKDIR /app

# 1) Copiamos package.json y package-lock.json
#    "npm ci" o "npm install" instalará TODO lo que está declarado ahí
COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com


# 2) Instalamos dependencias EXACTAS
RUN npm ci

# 3) Copiamos el resto del código (src/, public/, index.html, vite.config.js, etc.)
COPY . .

# 4) Construimos el bundle de producción con Vite
RUN npm run build

####################################
# Etapa 2: Servir estáticos con Nginx #
####################################
FROM nginx:stable-alpine

# 5) Limpiamos los archivos predeterminados de Nginx
RUN rm -rf /usr/share/nginx/html/* \
    && rm /etc/nginx/conf.d/default.conf

# 6) Copiamos nuestro nginx.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf

# 7) Copiamos el resultado del build (dist/) al directorio que Nginx sirve
COPY --from=builder /app/dist /usr/share/nginx/html

# 8) Exponemos el puerto 80
EXPOSE 80

# 9) Arrancamos Nginx en primer plano
CMD ["nginx", "-g", "daemon off;"]
