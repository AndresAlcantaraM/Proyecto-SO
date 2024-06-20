import docker
import time
import hashlib
import io
import json
import os

# Archivo donde se guardarán los comandos y ejecuciones
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
        
        # Esperar el tiempo estimado
        time.sleep(tiempo_estimado)

        # Detener y eliminar el contenedo
        contenedor.stop()
        contenedor.remove()
        print(f"El contenedor para el comando '{comando}' ha sido detenido y eliminado.")
    
    print(f"Esperando {tiempo_inicio} segundos para iniciar el contenedor para el comando '{comando}'...")
    time.sleep(tiempo_inicio)
    ejecutar_contenedor()

def guardar_comandos_ejecucion(comandos):
    if not os.path.exists(ARCHIVO_COMANDOS):
        with open(ARCHIVO_COMANDOS, 'w') as f:
            json.dump([], f)
    
    with open(ARCHIVO_COMANDOS, 'r') as f:
        ejecuciones_guardadas = json.load(f)
    
    ejecuciones_guardadas.append({
        "comandos": comandos
    })
    
    with open(ARCHIVO_COMANDOS, 'w') as f:
        json.dump(ejecuciones_guardadas, f, indent=4)

def listar_ejecuciones():
    if not os.path.exists(ARCHIVO_COMANDOS):
        return []
    
    with open(ARCHIVO_COMANDOS, 'r') as f:
        ejecuciones_guardadas = json.load(f)
    
    return ejecuciones_guardadas

def borrar_comandos_guardados():
    if os.path.exists(ARCHIVO_COMANDOS):
        with open(ARCHIVO_COMANDOS, 'w') as f:
            json.dump([], f)
        print("Comandos guardados borrados.")

def ejecutar_fifo(cliente, ejecucion):
    for cmd in ejecucion['comandos']:
        nombre_imagen = construir_imagen(cliente, cmd['comando'])
        crear_y_ejecutar_contenedor(cliente, nombre_imagen, cmd['comando'], cmd['tiempo_inicio'], cmd['tiempo_estimado'])

def ejecutar_round_robin(cliente, ejecucion, quantum=2):
    import threading

    def ejecutar_contenedor_round_robin(cmd):
        nombre_imagen = construir_imagen(cliente, cmd['comando'])
        nombre_contenedor = f"contenedor_{hashlib.md5(cmd['comando'].encode()).hexdigest()}"
        
        # Verificar si un contenedor con el mismo nombre ya existe y eliminarlo
        try:
            contenedor_existente = cliente.containers.get(nombre_contenedor)
            contenedor_existente.remove(force=True)
        except docker.errors.NotFound:
            pass

        contenedor = cliente.containers.run(nombre_imagen, detach=True, name=nombre_contenedor)
        total_time = cmd['tiempo_estimado']
        
        while total_time > 0:
            current_quantum = min(quantum, total_time)
            time.sleep(current_quantum)
            total_time -= current_quantum
            print(f"Quantum de {current_quantum}s ejecutado para el comando '{cmd['comando']}'. Restante: {total_time}s")
        
        contenedor.stop()
        contenedor.remove()
        print(f"El comando '{cmd['comando']}' ha terminado su ejecución.")

    threads = []
    for cmd in ejecucion['comandos']:
        t = threading.Thread(target=ejecutar_contenedor_round_robin, args=(cmd,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

def principal():
    cliente = docker.from_env()
    
    while True:
        print("\nOpciones:")
        print("1. Ingresar nuevos comandos")
        print("2. Listar y seleccionar ejecución guardada")
        print("3. Salir")
        opcion = input("Seleccione una opción: ")
        
        if opcion == '1':
            comandos = []
            while True:
                comando = input("Ingrese el comando (o 'no' para finalizar): ")
                if comando.lower() == 'no':
                    break
                tiempo_inicio = int(input("Ingrese el tiempo de inicio en segundos: "))
                tiempo_estimado = int(input("Ingrese el tiempo estimado de ejecución en segundos: "))
                comandos.append({
                    "comando": comando,
                    "tiempo_inicio": tiempo_inicio,
                    "tiempo_estimado": tiempo_estimado
                })
            
            guardar_comandos_ejecucion(comandos)
            for cmd in comandos:
                nombre_imagen = construir_imagen(cliente, cmd['comando'])
                crear_y_ejecutar_contenedor(cliente, nombre_imagen, cmd['comando'], cmd['tiempo_inicio'], cmd['tiempo_estimado'])
        
        elif opcion == '2':
            ejecuciones_guardadas = listar_ejecuciones()
            if not ejecuciones_guardadas:
                print("No hay ejecuciones guardadas.")
                continue
            
            for idx, ejec in enumerate(ejecuciones_guardadas):
                print(f"Ejecución {idx + 1}:")
                for cmd in ejec['comandos']:
                    print(f"  Comando: {cmd['comando']}, Tiempo de inicio: {cmd['tiempo_inicio']}s, Tiempo estimado: {cmd['tiempo_estimado']}s")
            
            seleccion = int(input("Seleccione la ejecución a ejecutar: ")) - 1
            if 0 <= seleccion < len(ejecuciones_guardadas):
                ejecucion_seleccionada = ejecuciones_guardadas[seleccion]
                print("Seleccione el algoritmo de planificación:")
                print("1. FIFO")
                print("2. Round Robin")
                algoritmo = input("Seleccione un algoritmo: ")
                if algoritmo == '1':
                    ejecutar_fifo(cliente, ejecucion_seleccionada)
                elif algoritmo == '2':
                    ejecutar_round_robin(cliente, ejecucion_seleccionada)
                else:
                    print("Algoritmo no válido.")
            else:
                print("Selección inválida.")
        
        elif opcion == '3':
            borrar_comandos_guardados()
            break
        else:
            print("Opción no válida, intente nuevamente.")

if __name__ == "__main__":
    principal()
