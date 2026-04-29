#!/bin/bash

# Script para inicializar la base de datos con Alembic

echo "Inicializando base de datos con Alembic..."

# Esperar a que la DB esté lista
echo "Esperando a que PostgreSQL esté disponible..."
until docker exec sc_database pg_isready -U sc_user -d semantic_db > /dev/null 2>&1; do
    echo "  Esperando..."
    sleep 2
done

echo "PostgreSQL está disponible!"

# Correr migraciones
echo "Corriendo migraciones..."
docker exec sc_api alembic upgrade head

echo "¡Base de datos inicializada!"
echo "API disponible en http://localhost:8000"
echo "Swagger UI en http://localhost:8000/docs"
