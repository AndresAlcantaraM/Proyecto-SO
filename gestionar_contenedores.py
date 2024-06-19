import docker
import time
import hashlib
import io

def generar_dockerfile(comando):
    contenido_dockerfile = f"""
    FROM ubuntu:latest
    ARG CMD
    CMD {comando}
    """
    return contenido_dockerfile

def construir_imagen(cliente, comando):
    hash_comando = hashlib.md5(comando.encode()).hexdigest()
    nombre_imagen = f"imagen_personalizada_{hash_comando}"
    
    try:
        cliente.images.get(nombre_imagen)
        print(f"La imagen para el comando '{comando}' ya existe. Usando la imagen existente.")
    except docker.errors.ImageNotFound:
        print(f"Construyendo imagen para el comando '{comando}'...")
        contenido_dockerfile = generar_dockerfile(comando)
        cliente.images.build(fileobj=io.BytesIO(contenido_dockerfile.encode('utf-8')), tag=nombre_imagen)
        print(f"Imagen para el comando '{comando}' construida exitosamente.")
    
    return nombre_imagen

def crear_y_ejecutar_contenedor(cliente, nombre_imagen, comando, tiempo_inicio, tiempo_estimado):
    nombre_contenedor = f"contenedor_{hashlib.md5(comando.encode()).hexdigest()}"
    
    def ejecutar_contenedor():
        print(f"Iniciando contenedor para el comando '{comando}'...")
        contenedor = cliente.containers.run(nombre_imagen, detach=True, name=nombre_contenedor)
        print(f"El contenedor para el comando '{comando}' está en ejecución.")
        time.sleep(tiempo_estimado)
        contenedor.stop()
        print(f"El contenedor para el comando '{comando}' se ha detenido.")
    
    print(f"Esperando {tiempo_inicio} segundos para iniciar el contenedor para el comando '{comando}'...")
    time.sleep(tiempo_inicio)
    ejecutar_contenedor()

def principal():
    cliente = docker.from_env()
    comandos = []

    while True:
        comando = input("Ingrese el comando (o 'salir' para finalizar): ")
        if comando.lower() == 'salir':
            break
        tiempo_inicio = int(input("Ingrese el tiempo de inicio en segundos: "))
        tiempo_estimado = int(input("Ingrese el tiempo estimado de ejecución en segundos: "))
        comandos.append((comando, tiempo_inicio, tiempo_estimado))

    for comando, tiempo_inicio, tiempo_estimado in comandos:
        nombre_imagen = construir_imagen(cliente, comando)
        crear_y_ejecutar_contenedor(cliente, nombre_imagen, comando, tiempo_inicio, tiempo_estimado)

if __name__ == "__main__":
    principal()
