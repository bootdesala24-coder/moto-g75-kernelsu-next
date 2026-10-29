#!/system/bin/sh
# Executado pelo proprietario via Magisk. Nao grava particoes e nao apaga modulos.
set -eu
umask 077

falhar() { echo "ERRO: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || falhar "Acesso root necessario."
[ "$(getprop ro.boot.hardware.sku)" = XT2437-1 ] || falhar "Modelo diferente do XT2437-1 analisado."
[ "$(getprop ro.build.display.id)" = W1UQ36H.73-38 ] || falhar "Firmware mudou; nao use este pacote."
[ "$(getprop ro.boot.slot_suffix)" = _a ] || falhar "Slot atual diferente de a."

g75_boot=$(sha256sum /dev/block/by-name/boot_a)
g75_init=$(sha256sum /dev/block/by-name/init_boot_a)
[ "${g75_boot%% *}" = 55c2ccece3ef93e0daba10a8b8a9332f83d3dcf6437cfaa973678851776c4c71 ] || falhar "Boot atual mudou."
[ "${g75_init%% *}" = eaaa88a4d55572e34510fba22066f7f9c4eb3837fb463b63e9221680fad8514c ] || falhar "Init_boot atual mudou."

g75_backup=/data/adb/g75-magisk-backup-20261029
[ ! -e "$g75_backup" ] && [ ! -L "$g75_backup" ] || falhar "Backup de modulos ja existe. Nao repita a preparacao."
g75_pastas="modules modules_update post-fs-data.d service.d post-mount.d boot-completed.d"
for g75_nome in $g75_pastas; do
    g75_origem=/data/adb/$g75_nome
    [ ! -L "$g75_origem" ] || falhar "Caminho inesperado: $g75_origem e um link."
    if [ -e "$g75_origem" ] && [ ! -d "$g75_origem" ]; then
        falhar "Caminho inesperado: $g75_origem nao e uma pasta."
    fi
done
mkdir "$g75_backup"
for g75_nome in $g75_pastas; do
    g75_origem=/data/adb/$g75_nome
    if [ -d "$g75_origem" ]; then
        mv "$g75_origem" "$g75_backup/$g75_nome" || falhar "Falha ao guardar $g75_nome. Preserve o backup e nao prossiga."
        echo "Guardado: $g75_nome"
    fi
done
echo "XT2437-1 W1UQ36H.73-38 slot a" > "$g75_backup/preparado.txt"
echo "PREPARACAO_OK"
echo "Backup dos modulos e scripts: $g75_backup"
