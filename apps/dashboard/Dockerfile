FROM node:22.22.2-alpine AS builder
WORKDIR /app
COPY apps/dashboard/package*.json ./
RUN npm ci
COPY apps/dashboard/ ./
ARG TOLLGATE_API_URL=http://gateway:8187
ENV TOLLGATE_API_URL=$TOLLGATE_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22.22.2-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3187 NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 10001 -S tollgate && adduser -S -u 10001 -G tollgate tollgate
COPY --from=builder --chown=tollgate:tollgate /app/.next/standalone ./
COPY --from=builder --chown=tollgate:tollgate /app/.next/static ./.next/static
USER tollgate
EXPOSE 3187
HEALTHCHECK --interval=15s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1:3187/login || exit 1
CMD ["node", "server.js"]
