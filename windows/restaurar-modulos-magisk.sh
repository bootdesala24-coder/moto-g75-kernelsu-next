#!/system/bin/sh
# Opcional: somente depois de restaurar boot/init_boot Magisk e iniciar Android.
set -eu
umask 077
falhar() { echo "ERRO: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || falhar "Acesso root necessario."
[ "$(getprop ro.boot.hardware.sku)" = XT2437-1 ] || falhar "Modelo inesperado."
g75_backup=/data/adb/g75-magisk-backup-20261029
[ -d "$g75_backup" ] && [ ! -L "$g75_backup" ] || falhar "Backup de modulos nao encontrado."
g75_pastas="modules modules_update post-fs-data.d service.d post-mount.d boot-completed.d"
for g75_nome in $g75_pastas; do
    if [ -d "$g75_backup/$g75_nome" ]; then
        g75_destino=/data/adb/$g75_nome
        [ ! -L "$g75_destino" ] || falhar "Destino e um link; nada sera substituido."
        if [ -e "$g75_destino" ]; then
            [ -d "$g75_destino" ] || falhar "Destino nao e pasta."
            [ -z "$(ls -A "$g75_destino")" ] || falhar "Destino contem novos arquivos: $g75_destino. Nada sera sobrescrito."
        fi
    fi
done
for g75_nome in $g75_pastas; do
    if [ -d "$g75_backup/$g75_nome" ]; then
        g75_destino=/data/adb/$g75_nome
        if [ -d "$g75_destino" ]; then rmdir "$g75_destino"; fi
        mv "$g75_backup/$g75_nome" "$g75_destino"
    fi
done
echo "MODULOS_RESTAURADOS. Reinicie o Android para voltar a carrega-los."
