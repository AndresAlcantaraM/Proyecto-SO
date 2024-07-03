CREATE TABLE ejecuciones (
    id SERIAL PRIMARY KEY,
    algoritmo VARCHAR(50) NOT NULL,
    avg_response_time FLOAT,
    avg_turnaround_time FLOAT
);

CREATE TABLE comandos(
    id SERIAL PRIMARY KEY,
    ejecucion_id INT REFERENCES ejecuciones(id),
    comando VARCHAR(255) NOT NULL,
    tiempo_inicio INT NOT NULL,
    tiempo_estimado INT NOT NULL,
    imagen VARCHAR(255) NOT NULL,
    tiempo_final INT,
    response_time INT,
    turnaround_time INT
)
