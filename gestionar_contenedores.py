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
        # Esperar el tiempo estimado
        time.sleep(tiempo_estimado)
        contenedor.stop()
        print(f"El contenedor para el comando '{comando}' ha sido ejecutado.")
    
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
        

def fcfs(comandos):
    comandos_ordenados = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    
    for comando in comandos_ordenados:
        tiempo_actual = max(tiempo_actual, comando['tiempo_inicio'])
        tiempo_actual += comando['tiempo_estimado']
        comando['tiempo_final'] = tiempo_actual
    
    return comandos_ordenados


def round_robin(comandos, quantum=2):
    tiempo_actual = 0
    cola = []
    comandos_ordenados = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    
    indice = 0
    for comando in comandos_ordenados:
        comando['restante'] = comando['tiempo_estimado']
        comando['iniciado'] = False

    while cola or indice < len(comandos_ordenados):
        if not cola:
            if indice < len(comandos_ordenados):
                tiempo_actual = comandos_ordenados[indice]['tiempo_inicio']
                while indice < len(comandos_ordenados) and comandos_ordenados[indice]['tiempo_inicio'] <= tiempo_actual:
                    cola.append(comandos_ordenados[indice])
                    indice += 1
        
        comando_actual = cola.pop(0)

        if not comando_actual['iniciado']:
            comando_actual['iniciado'] = True
            comando_actual['inicio_efectivo'] = tiempo_actual

        tiempo_ejecucion = min(quantum, comando_actual['restante'])
        
        comando_actual['restante'] -= tiempo_ejecucion
        
        tiempo_actual += tiempo_ejecucion
        
        while indice < len(comandos_ordenados) and comandos_ordenados[indice]['tiempo_inicio'] <= tiempo_actual:
            cola.append(comandos_ordenados[indice])
            indice += 1
        
        # Si el comando aún no ha terminado, reinsertarlo al final de la cola
        if comando_actual['restante'] > 0:
            cola.append(comando_actual)
        else:
            # Si el comando ha terminado, registrar su tiempo de finalización
            comando_actual['tiempo_final'] = tiempo_actual
    
    return comandos_ordenados

def spn(comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []
    
    while cola:
        comando = min(cola, key=lambda x: x['tiempo_estimado'] if x['tiempo_inicio'] <= tiempo_actual else float('inf'))
        if comando['tiempo_inicio'] > tiempo_actual:
            tiempo_actual = comando['tiempo_inicio']
        cola.remove(comando)
        tiempo_actual += comando['tiempo_estimado']
        comando['tiempo_final'] = tiempo_actual
        resultados.append(comando)
    
    return resultados


def srt(comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []
    tiempos_restantes = {cmd['comando']: cmd['tiempo_estimado'] for cmd in cola}
    en_ejecucion = []

    while cola or en_ejecucion:
        while cola and cola[0]['tiempo_inicio'] <= tiempo_actual:
            en_ejecucion.append(cola.pop(0))

        if en_ejecucion:
            comando = min(en_ejecucion, key=lambda x: tiempos_restantes[x['comando']])
            en_ejecucion.remove(comando)
            tiempo_ejecucion = 1  # Ejecutar en unidades de tiempo de 1
            tiempos_restantes[comando['comando']] -= tiempo_ejecucion
            tiempo_actual += tiempo_ejecucion

            if tiempos_restantes[comando['comando']] > 0:
                en_ejecucion.append(comando)
            else:
                comando['tiempo_final'] = tiempo_actual
                resultados.append(comando)
        else:
            tiempo_actual += 1

    return resultados


def hrrn(comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []
    
    while cola:
        for comando in cola:
            espera = max(0, tiempo_actual - comando['tiempo_inicio'])
            ratio = (espera + comando['tiempo_estimado']) / comando['tiempo_estimado']
            comando['response_ratio'] = ratio
        
        comando = max(cola, key=lambda x: x['response_ratio'] if x['tiempo_inicio'] <= tiempo_actual else -1)
        if comando['tiempo_inicio'] > tiempo_actual:
            tiempo_actual = comando['tiempo_inicio']
        cola.remove(comando)
        tiempo_actual += comando['tiempo_estimado']
        comando['tiempo_final'] = tiempo_actual
        resultados.append(comando)
    
    return resultados


def calcular_tiempos(comandos):
    turnaround_times = []
    response_times = []
    
    for comando in comandos:
        turnaround_time = comando['tiempo_final'] - comando['tiempo_inicio']
        response_time = comando['tiempo_final'] - comando['tiempo_inicio'] - comando['tiempo_estimado']
        turnaround_times.append(turnaround_time)
        response_times.append(response_time)
        
        comando['turnaround_time'] = turnaround_time
        comando['response_time'] = response_time
    
    avg_turnaround_time = sum(turnaround_times) / len(turnaround_times)
    avg_response_time = sum(response_times) / len(response_times)
    
    return {
        'turnaround_times': turnaround_times,
        'response_times': response_times,
        'avg_turnaround_time': avg_turnaround_time,
        'avg_response_time': avg_response_time
    }


def principal():
    cliente = docker.from_env()
    ejecuciones = []

    while True:
        print("\nOpciones:")
        print("1. Ingresar nuevo comando")
        print("2. Listar y seleccionar comando guardado")
        print("3. Listar ejecuciones anteriores")
        print("4. Salir")
        opcion = input("Seleccione una opción: ")
        
        if opcion == '1':
            comandos = []
            while True:
                comando = input("Ingrese el comando (o 'salir' para finalizar): ")
                if comando.lower() == 'salir':
                    break
                try:
                    tiempo_inicio = int(input("Ingrese el tiempo de inicio en segundos: "))
                    tiempo_estimado = int(input("Ingrese el tiempo estimado de ejecución en segundos: "))
                except ValueError:
                    print("Por favor ingrese valores válidos para los tiempos.")
                    continue

                nombre_imagen = construir_imagen(cliente, comando)
                comandos.append({
                    "comando": comando,
                    "tiempo_inicio": tiempo_inicio,
                    "tiempo_estimado": tiempo_estimado,
                    "imagen": nombre_imagen
                })
            
            guardar_comandos_ejecucion(comandos)
        
        elif opcion == '2':
            ejecuciones_guardadas = listar_ejecuciones()
            if not ejecuciones_guardadas:
                print("No hay comandos guardados.")
                continue
            
            for idx, ejec in enumerate(ejecuciones_guardadas):
                print(f"\nEjecución {idx + 1}:")
                for cmd in ejec['comandos']:
                    print(f"  Comando: {cmd['comando']}, Tiempo de inicio: {cmd['tiempo_inicio']}s, Tiempo estimado: {cmd['tiempo_estimado']}s, Imagen: {cmd['imagen']}")
            
            seleccion = int(input("\nSeleccione la ejecución a ejecutar: ")) - 1
            if 0 <= seleccion < len(ejecuciones_guardadas):
                ejecucion_seleccionada = ejecuciones_guardadas[seleccion]
                print("\nAlgoritmos de Planificación:")
                print("1. First Come First Served (FCFS)")
                print("2. Round Robin")
                print("3. Shortest Process Next (SPN)")
                print("4. Shortest Remaining Time (SRT)")
                print("5. Highest Response Ratio Next (HRRN)")

                algoritmo = input("\nSeleccione un algoritmo: ")
            
                if algoritmo == '1':
                    comandos_planificados = fcfs(ejecucion_seleccionada['comandos'])
                elif algoritmo == '2':
                    comandos_planificados = round_robin(ejecucion_seleccionada['comandos'])
                elif algoritmo == '3':
                    comandos_planificados = spn(ejecucion_seleccionada['comandos'])
                elif algoritmo == '4':
                    comandos_planificados = srt(ejecucion_seleccionada['comandos'])
                elif algoritmo == '5':
                    comandos_planificados = hrrn(ejecucion_seleccionada['comandos'])
                else:
                    print("Selección inválida.")
                    continue

                tiempos = calcular_tiempos(comandos_planificados)
                ejecuciones.append({
                    'comandos': comandos_planificados,
                    'algoritmo': algoritmo,
                    'tiempos': tiempos
                })

                for comando in comandos_planificados:
                    crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'], comando['tiempo_inicio'], comando['tiempo_estimado'])
                
                print("\nTiempos calculados:")
                print(f"Turnaround time promedio: {tiempos['avg_turnaround_time']}")
                print(f"Response time promedio: {tiempos['avg_response_time']}")
        
        elif opcion == '3':
            if not ejecuciones:
                print("No hay ejecuciones anteriores.")
                continue
            
            for idx, ejecucion in enumerate(ejecuciones):
                print(f"\nEjecución {idx + 1}:")
                print(f"Algoritmo: {ejecucion['algoritmo']}")
                for comando in ejecucion['comandos']:
                    print(f"Comando: {comando['comando']}, Turnaround time: {comando['turnaround_time']}, Response time: {comando['response_time']}")
                print(f"Turnaround time promedio: {ejecucion['tiempos']['avg_turnaround_time']}")
                print(f"Response time promedio: {ejecucion['tiempos']['avg_response_time']}")
        
        elif opcion == '4':
            borrar_comandos_guardados()
            break
        else:
            print("Opción no válida, intente nuevamente.")

if __name__ == "__main__":
    principal()
