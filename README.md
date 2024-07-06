# Proyecto-SO

Proyecto final de la asignatura de sistemas operativos que  implementa y evalua varios algoritmos de planificación de procesos dentro de un entorno virtualizado utilizando Docker. Teniendo como procesos contenedores de docker que se ejecutan en un sistema operativo.

El proyecto se desarrollo en python, en donde se utilizo la libreria psycopg2 para realizar la conexión a la base de datos (PostgreSQL).


## Integrantes
Andrés Felipe Alcántara Muñoz 2242517

Miguel Ángel Salcedo Urian 2242786

## Inicialización

Una vez dentro de la carpeta raíz del proyecto procedemos a crear el contenedor para la base de datos (debe tener Docker en ejecución):
```sh
docker build -t imagen_proyecto .
docker run --name contenedor_proyecto -p 5432:5432 -e POSTGRES_PASSWORD=pg123 -d imagen_proyecto
```
Despues de crear el servidor de la base de datos mediante la conexión al contenedor, debemos tener en cuenta que se debe actualizar la dirección ip y la contraseña de la base de datos (en caso de no haber usado la del documento).

Verificamos tener instalados los siguientes requisitos:
```sh
psycopg2: pip install psycopg2
docker: pip install docker
```
Debemos cambiar el host de la base de datos proporcionando nuestra dirección ip en la linea 12 del código y cambiar la contraseña de la base de datos (si no utilizó la proporcionada en el documento):
```py
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "pg123" #Modificar si lo necesita
DB_HOST = "Tu dirección ip aquí"
```
Finalmente ejecutamos el archivo Gestionar_contenedores.py, para acceder al menu de la aplicacion
```sh
python Gestionar_contenedores.py
```
