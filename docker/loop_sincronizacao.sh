#!/bin/sh
# Substitui o Agendador de Tarefas do Windows: roda uma sincronização a cada
# INTERVALO_SEGUNDOS, alinhada ao relógio (60 -> 12:00, 12:01, 12:02...),
# e uma logo ao subir o container.
# Execuções nunca se sobrepõem (não há lock entre elas): se uma passar do
# próximo horário, a seguinte espera o horário depois dela.
#
# SIGTERM (docker compose stop/down, restart do Docker Desktop) NÃO interrompe
# uma execução em andamento: matar no meio pode postar um followup sem gravar
# a auditoria, e ele seria repostado na execução seguinte. O sinal só marca a
# parada; o loop sai quando a execução atual termina.
INTERVALO="${INTERVALO_SEGUNDOS:-60}"
PARAR=0
trap 'PARAR=1' TERM INT

validar_intervalo() {
    # Só divisor de 3600 alinha igual em toda hora (7 min cairia em 12:56, 13:03...).
    case "$INTERVALO" in
        ''|*[!0-9]*) ;;
        *) [ "$INTERVALO" -gt 0 ] && [ $((3600 % INTERVALO)) -eq 0 ] && return 0 ;;
    esac
    echo "INTERVALO_SEGUNDOS=$INTERVALO inválido: esperado divisor de 3600 em segundos (ex.: 60)" >&2
    exit 1
}

segundos_ate_proximo_horario() {
    # Epoch múltiplo de INTERVALO = minuto cheio local (fuso de Brasília tem offset de horas inteiras).
    agora=$(date +%s)
    echo $((INTERVALO - agora % INTERVALO))
}

aguardar_processo() {
    # `wait` retorna cedo quando um sinal chega; espera de novo até o PID sumir.
    while kill -0 "$1" 2>/dev/null; do
        wait "$1"
    done
}

executar_sincronizacao() {
    # Python fora do grupo de sinais do shell: o TERM do Docker vai só pro PID 1.
    python glpi_tiflux.py &
    aguardar_processo $!
}

validar_intervalo
# Ao subir o container roda um ciclo na hora, sem esperar o próximo horário;
# depois segue alinhado ao relógio.
executar_sincronizacao
while [ "$PARAR" -eq 0 ]; do
    sleep "$(segundos_ate_proximo_horario)" &
    PID_SLEEP=$!
    wait "$PID_SLEEP"
    kill "$PID_SLEEP" 2>/dev/null
    [ "$PARAR" -eq 1 ] && break

    executar_sincronizacao
done

echo "Parada solicitada — encerrando após a última execução."
