import docker
import time
import hashlib
import io
import json
import os

# Archivo donde se guardarán los comandos
ARCHIVO_COMANDOS = "comandos.json"

def generar_dockerfile(comando):
    contenido_dockerfile = f"""
    FROM ubuntu:latest
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
        # Verificar si un contenedor con el mismo nombre ya existe y eliminarlo
        try:
            contenedor_existente = cliente.containers.get(nombre_contenedor)
            print(f"Eliminando contenedor existente con el nombre '{nombre_contenedor}'...")
            contenedor_existente.remove(force=True)
            print(f"Contenedor existente '{nombre_contenedor}' eliminado.")
        except docker.errors.NotFound:
            pass  # No existe un contenedor con ese nombre, podemos continuar

        print(f"Iniciando contenedor para el comando '{comando}'...")
        contenedor = cliente.containers.run(nombre_imagen, detach=True, name=nombre_contenedor)
        print(f"El contenedor para el comando '{comando}' está en ejecución.")
        try:
            contenedor.wait(timeout=tiempo_estimado)
            print(f"El contenedor para el comando '{comando}' ha terminado su ejecución.")
        except docker.errors.ContainerError as e:
            print(f"Error en la ejecución del contenedor: {e}")
        except docker.errors.APIError as e:
            print(f"Error en la API de Docker: {e}")
        except docker.errors.DockerException as e:
            print(f"Error desconocido en Docker: {e}")
            
    print(f"Esperando {tiempo_inicio} segundos para iniciar el contenedor para el comando '{comando}'...")
    time.sleep(tiempo_inicio)
    ejecutar_contenedor()

def guardar_comando(comando, tiempo_inicio, tiempo_estimado):
    if not os.path.exists(ARCHIVO_COMANDOS):
        with open(ARCHIVO_COMANDOS, 'w') as f:
            json.dump([], f)
    
    with open(ARCHIVO_COMANDOS, 'r') as f:
        comandos_guardados = json.load(f)
    
    comandos_guardados.append({
        "comando": comando,
        "tiempo_inicio": tiempo_inicio,
        "tiempo_estimado": tiempo_estimado
    })
    
    with open(ARCHIVO_COMANDOS, 'w') as f:
        json.dump(comandos_guardados, f, indent=4)

def listar_comandos():
    if not os.path.exists(ARCHIVO_COMANDOS):
        return []
    
    with open(ARCHIVO_COMANDOS, 'r') as f:
        comandos_guardados = json.load(f)
    
    return comandos_guardados

def principal():
    cliente = docker.from_env()
    
    while True:
        print("\nOpciones:")
        print("1. Ingresar nuevo comando")
        print("2. Listar y seleccionar comando guardado")
        print("3. Salir")
        opcion = input("Seleccione una opción: ")
        
        if opcion == '1':
            comando = input("Ingrese el comando: ")
            tiempo_inicio = int(input("Ingrese el tiempo de inicio en segundos: "))
            tiempo_estimado = int(input("Ingrese el tiempo estimado de ejecución en segundos: "))
            guardar_comando(comando, tiempo_inicio, tiempo_estimado)
            nombre_imagen = construir_imagen(cliente, comando)
            crear_y_ejecutar_contenedor(cliente, nombre_imagen, comando, tiempo_inicio, tiempo_estimado)
        
        elif opcion == '2':
            comandos_guardados = listar_comandos()
            if not comandos_guardados:
                print("No hay comandos guardados.")
                continue
            
            for idx, cmd in enumerate(comandos_guardados):
                print(f"{idx + 1}. Comando: {cmd['comando']}, Tiempo de inicio: {cmd['tiempo_inicio']}s, Tiempo estimado: {cmd['tiempo_estimado']}s")
            
            seleccion = int(input("Seleccione el comando a ejecutar: ")) - 1
            if 0 <= seleccion < len(comandos_guardados):
                comando_seleccionado = comandos_guardados[seleccion]
                nombre_imagen = construir_imagen(cliente, comando_seleccionado['comando'])
                crear_y_ejecutar_contenedor(cliente, nombre_imagen, comando_seleccionado['comando'], comando_seleccionado['tiempo_inicio'], comando_seleccionado['tiempo_estimado'])
            else:
                print("Selección inválida.")
        
        elif opcion == '3':
            break
        else:
            print("Opción no válida, intente nuevamente.")

if __name__ == "__main__":
    principal()
