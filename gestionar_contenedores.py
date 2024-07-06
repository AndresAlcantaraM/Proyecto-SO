import time
import docker
import hashlib
import io
import psycopg2

DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "pg123"
DB_HOST = "Tu dirección ip aquí"

def conectar_db():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )


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


def crear_y_ejecutar_contenedor(cliente, nombre_imagen, comando):
    nombre_contenedor = f"contenedor_{hashlib.md5(comando.encode()).hexdigest()}"
    
    # Verificar si un contenedor con el mismo nombre ya existe y eliminarlo
    try:
        contenedor_existente = cliente.containers.get(nombre_contenedor)
        print(f"Eliminando contenedor existente con el nombre '{nombre_contenedor}'...")
        contenedor_existente.remove(force=True)
        print(f"Contenedor existente '{nombre_contenedor}' eliminado.")
    except docker.errors.NotFound:
        pass  # No existe un contenedor con ese nombre, se continúa la ejecución

    print(f"Iniciando contenedor para el comando '{comando}'...")
    contenedor = cliente.containers.run(nombre_imagen, detach=True, name=nombre_contenedor)
    print(f"El contenedor para el comando '{comando}' está en ejecución.")
    
    return contenedor


def guardar_comandos_ejecucion(comandos, algoritmo):
    conn = conectar_db()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO ejecuciones (algoritmo)
        VALUES (%s) RETURNING id
    """, (algoritmo,))
    ejecucion_id = cur.fetchone()[0]
    
    for comando in comandos:
        cur.execute("""
            INSERT INTO comandos (ejecucion_id, comando, tiempo_inicio, tiempo_estimado, imagen)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (ejecucion_id, comando['comando'], comando['tiempo_inicio'], comando['tiempo_estimado'], comando['imagen']))
        comando_id = cur.fetchone()[0]
        comando['id'] = comando_id
    
    conn.commit()
    cur.close()
    conn.close()


def listar_ejecuciones():
    conn = conectar_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, algoritmo, avg_response_time, avg_turnaround_time FROM ejecuciones
    """)
    ejecuciones = cur.fetchall()
    
    ejecuciones_guardadas = []  
    for ejec in ejecuciones:
        cur.execute("""
            SELECT comando, tiempo_inicio, tiempo_estimado, imagen, id
            FROM comandos WHERE ejecucion_id = %s
        """, (ejec[0],))
        comandos = cur.fetchall()
        ejecuciones_guardadas.append({
            'id_ejec': ejec[0],
            'algoritmo': ejec[1],
            'avg_response_time': ejec[2],
            'avg_turnaround_time': ejec[3],
            'comandos': [{'comando': cmd[0], 'tiempo_inicio': cmd[1], 'tiempo_estimado': cmd[2], 'imagen': cmd[3], 'id' : cmd[4]} for cmd in comandos]
        })
    
    cur.close()
    conn.close()
    return ejecuciones_guardadas

def actualizar_ejecucion(ejecucion_id, algoritmo, tiempos):
    conn = conectar_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE ejecuciones
        SET algoritmo = %s, avg_response_time = %s, avg_turnaround_time = %s
        WHERE id = %s
    """, (algoritmo, tiempos['avg_response_time'], tiempos['avg_turnaround_time'], ejecucion_id))
    
    conn.commit()
    cur.close()
    conn.close()

def actualizar_tiempos_comando(comando):
    conn = conectar_db()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE comandos
        SET tiempo_final = %s, response_time = %s, turnaround_time = %s
        WHERE id = %s
    """, (comando['tiempo_final'], comando['response_time'], comando['turnaround_time'], comando['id']))
    
    conn.commit()
    cur.close()
    conn.close()

def borrar_comandos_guardados():
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM comandos")
    cur.execute("DELETE FROM ejecuciones")
    conn.commit()
    cur.close()
    conn.close()
    print("Comandos guardados borrados.")

def fcfs(cliente, comandos):
    comandos_ordenados = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    
    for comando in comandos_ordenados:
        tiempo_actual = max(tiempo_actual, comando['tiempo_inicio'])
        contenedor = crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'])
        tiempo_actual += comando['tiempo_estimado']
        contenedor.stop()
        comando['tiempo_final'] = tiempo_actual
    
    return comandos_ordenados


def round_robin(cliente, comandos, quantum=2):
    tiempo_actual = 0
    cola = []
    comandos_ordenados = sorted(comandos, key=lambda x: x['tiempo_inicio'])

    indice = 0
    for comando in comandos_ordenados:
        comando['restante'] = comando['tiempo_estimado']
        comando['iniciado'] = False
        comando['contenedor'] = crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'])
        try:
            comando['contenedor'].pause()
        except docker.errors.APIError as e:
            pass

    while cola or indice < len(comandos_ordenados):
        if not cola:
            if indice < len(comandos_ordenados):
                tiempo_actual = comandos_ordenados[indice]['tiempo_inicio']
                while indice < len(comandos_ordenados) and comandos_ordenados[indice]['tiempo_inicio'] <= tiempo_actual:
                    cola.append(comandos_ordenados[indice])
                    indice += 1

        if cola:
            comando_actual = cola.pop(0)

            if not comando_actual['iniciado']:
                comando_actual['iniciado'] = True
                comando_actual['inicio_efectivo'] = tiempo_actual

            tiempo_ejecucion = min(quantum, comando_actual['restante'])

            comando_actual['restante'] -= tiempo_ejecucion

            try:
                comando_actual['contenedor'].unpause()
                time.sleep(tiempo_ejecucion)
                comando_actual['contenedor'].pause()
            except docker.errors.APIError as e:
                pass

            tiempo_actual += tiempo_ejecucion

            while indice < len(comandos_ordenados) and comandos_ordenados[indice]['tiempo_inicio'] <= tiempo_actual:
                cola.append(comandos_ordenados[indice])
                indice += 1

            if comando_actual['restante'] > 0:
                cola.append(comando_actual)
            else:
                comando_actual['tiempo_final'] = tiempo_actual
                comando_actual['contenedor'].stop()
        else:
            tiempo_actual += 1

    return comandos_ordenados

def spn(cliente, comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []

    # Crear una lista para mantener el orden original de los comandos
    comandos_originales = comandos[:]

    while cola:
        disponibles = [cmd for cmd in cola if cmd['tiempo_inicio'] <= tiempo_actual]

        if not disponibles:
            tiempo_actual = cola[0]['tiempo_inicio']
            continue

        comando = min(disponibles, key=lambda x: x['tiempo_estimado'])

        if comando['tiempo_inicio'] > tiempo_actual:
            tiempo_actual = comando['tiempo_inicio']

        comando['contenedor'] = crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'])
        
        tiempo_actual += comando['tiempo_estimado']
        comando['tiempo_final'] = tiempo_actual
        comando['contenedor'].stop()
        resultados.append(comando)

        cola.remove(comando)

    # Restaurar el orden original de los comandos
    resultados_ordenados = []
    for original in comandos_originales:
        for resultado in resultados:
            if resultado['imagen'] == original['imagen'] and resultado['comando'] == original['comando']:
                resultados_ordenados.append(resultado)
                break

    return resultados_ordenados


def srt(cliente, comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []
    tiempos_restantes = {cmd['comando']: cmd['tiempo_estimado'] for cmd in cola}
    en_ejecucion = []


    comandos_originales = comandos[:]

    for comando in cola:
        comando['contenedor'] = crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'])

    while cola or en_ejecucion:
        while cola and cola[0]['tiempo_inicio'] <= tiempo_actual:
            en_ejecucion.append(cola.pop(0))

        if en_ejecucion:
            comando = min(en_ejecucion, key=lambda x: tiempos_restantes[x['comando']])
            en_ejecucion.remove(comando)
            tiempo_ejecucion = 1  # Ejecutar en unidades de tiempo de 1

            try:
                if comando['contenedor'].status == 'paused':
                    comando['contenedor'].unpause()
            except docker.errors.APIError as e:
                print(f"Error al reanudar el contenedor {comando['contenedor'].id}: {e}")

            tiempos_restantes[comando['comando']] -= tiempo_ejecucion
            tiempo_actual += tiempo_ejecucion

            try:
                if comando['contenedor'].status == 'running':
                    comando['contenedor'].pause()
            except docker.errors.APIError as e:
                print(f"Error al pausar el contenedor {comando['contenedor'].id}: {e}")

            if tiempos_restantes[comando['comando']] > 0:
                en_ejecucion.append(comando)
            else:
                comando['tiempo_final'] = tiempo_actual
                resultados.append(comando)
        else:
            tiempo_actual += 1


    resultados_ordenados = []
    for original in comandos_originales:
        for resultado in resultados:
            if resultado['imagen'] == original['imagen'] and resultado['comando'] == original['comando']:
                resultados_ordenados.append(resultado)
                break

    return resultados_ordenados


def hrrn(cliente, comandos):
    cola = sorted(comandos, key=lambda x: x['tiempo_inicio'])
    tiempo_actual = 0
    resultados = []


    comandos_originales = comandos[:]


    for comando in cola:
        comando['contenedor'] = crear_y_ejecutar_contenedor(cliente, comando['imagen'], comando['comando'])

    while cola:
        # Calcula la razón de respuesta para cada proceso que ha llegado
        for comando in cola:
            if comando['tiempo_inicio'] <= tiempo_actual:
                espera = tiempo_actual - comando['tiempo_inicio']
                ratio = (espera + comando['tiempo_estimado']) / comando['tiempo_estimado']
                comando['response_ratio'] = ratio
            else:
                comando['response_ratio'] = -1  # No considerar procesos que no han llegado

        # Selecciona el proceso con la mayor razón de respuesta
        comando = max(cola, key=lambda x: x['response_ratio'])
        if comando['response_ratio'] == -1:
            tiempo_actual = cola[0]['tiempo_inicio']
            continue

        # Si el proceso aún no ha llegado, espera
        if comando['tiempo_inicio'] > tiempo_actual:
            tiempo_actual = comando['tiempo_inicio']

        # Ejecutar el comando
        try:
            if comando['contenedor'].status == 'paused':
                comando['contenedor'].unpause()
            time.sleep(comando['tiempo_estimado'])
            comando['contenedor'].stop()
        except docker.errors.APIError as e:
            pass

        cola.remove(comando)
        tiempo_actual += comando['tiempo_estimado']
        comando['tiempo_final'] = tiempo_actual
        resultados.append(comando)


    resultados_ordenados = []
    for original in comandos_originales:
        for resultado in resultados:
            if resultado['imagen'] == original['imagen'] and resultado['comando'] == original['comando']:
                resultados_ordenados.append(resultado)
                break

    return resultados_ordenados

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
        print("2. Listar, seleccionar y ejecutar bloque guardado")
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
                if nombre_imagen:
                    comandos.append({
                        "comando": comando,
                        "tiempo_inicio": tiempo_inicio,
                        "tiempo_estimado": tiempo_estimado,
                        "imagen": nombre_imagen,
                        "id": -1
                    })

            guardar_comandos_ejecucion(comandos, "")

        elif opcion == '2':
            ejecuciones_guardadas = listar_ejecuciones()
            if not ejecuciones_guardadas:
                print("No hay comandos guardados.")
                continue

            for idx, ejec in enumerate(ejecuciones_guardadas):
                print(f"\nEjecución {idx + 1}:")
                for cmd in ejec['comandos']:
                    print(f"  Comando: {cmd['comando']}, Tiempo de inicio: {cmd['tiempo_inicio']}s, Tiempo estimado: {cmd['tiempo_estimado']}s, Imagen: {cmd['imagen']}")

            try:
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
                        comandos_planificados = fcfs(cliente, ejecucion_seleccionada['comandos'])
                    elif algoritmo == '2':
                        comandos_planificados = round_robin(cliente, ejecucion_seleccionada['comandos'])
                    elif algoritmo == '3':
                        comandos_planificados = spn(cliente, ejecucion_seleccionada['comandos'])
                    elif algoritmo == '4':
                        comandos_planificados = srt(cliente, ejecucion_seleccionada['comandos'])
                    elif algoritmo == '5':
                        comandos_planificados = hrrn(cliente, ejecucion_seleccionada['comandos'])
                    else:
                        print("Selección inválida.")
                        continue

                    tiempos = calcular_tiempos(comandos_planificados)
                    ejecuciones.append({
                        'comandos': comandos_planificados,
                        'algoritmo': algoritmo,
                        'tiempos': tiempos
                    })

                    actualizar_ejecucion(ejecucion_seleccionada['id_ejec'], algoritmo, tiempos)

                    for comando in comandos_planificados:
                        actualizar_tiempos_comando(comando)
                    
                    print("\nTiempos calculados:")
                    print(f"Turnaround time promedio: {tiempos['avg_turnaround_time']}")
                    print(f"Response time promedio: {tiempos['avg_response_time']}")
                else:
                    print("Selección inválida.")
            except ValueError:
                print("Entrada inválida. Intente nuevamente.")

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
