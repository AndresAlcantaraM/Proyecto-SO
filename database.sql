CREATE TABLE ejecuciones (
    id SERIAL PRIMARY KEY,
    comandos JSONB NOT NULL,
    algoritmo VARCHAR(50) NOT NULL,
    tiempos JSONB NOT NULL
);
