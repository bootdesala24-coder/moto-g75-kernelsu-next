# Diagnóstico pelo Windows

O proprietário confirmou sistema original Motorola com **Magisk** e acesso a um
computador Windows. A coleta confirmou SKU **XT2437-1**, slot **a**, páginas de 4096
bytes e configuração do kernel idêntica à referência Google. A versão do Magisk
ainda não foi coletada. O estado de bootloader informado por `getprop` foi `locked`,
mas uma foto posterior da inicialização mostra **The boot loader is unlocked**.
A opção Desbloqueio de OEM desligada não bloqueia novamente o bootloader. A consulta
abaixo fica documentada como verificação adicional; não é preciso refazer o
desbloqueio. A causa da propriedade divergente no Android não foi determinada.

1. Obtenha o [Android SDK Platform-Tools oficial para Windows](https://developer.android.com/tools/releases/platform-tools) e extraia o ZIP.
2. Baixe `coletar-dados.cmd` deste repositório e coloque-o na pasta que contém `adb.exe`.
3. No telefone, habilite **Depuração USB** em **Sistema → Opções do desenvolvedor**.
4. Conecte somente esse telefone por USB e autorize esse computador na tela do telefone.
5. Abra `coletar-dados.cmd`. Ele cria uma pasta `diagnostico-g75-...` ao lado do arquivo.
6. Envie `aparelho.txt` e, se tiver sido obtido, `kernel-config.gz` na conversa.

O script consulta propriedades selecionadas, versão do kernel, tamanho de página,
estado SELinux e nomes das partições. Ele tenta copiar `/proc/config.gz` usando ADB;
se o arquivo não existir ou não for acessível, o erro ficará no relatório e os demais
dados ainda serão úteis. Não pede IMEI, número de telefone ou número de série.

Esse coletor não executa `su`, não instala aplicativos, não remove Magisk, não reinicia
o telefone, não escreve nas partições e não faz backup de boot. A coleta permite
preparar os comandos de backup corretos depois de confirmar o layout do aparelho.

O `boot.img` atual pode estar modificado pelo Magisk. Uma cópia dele não deve ser
identificada como firmware original sem a verificação correspondente. A migração
para KernelSU Next precisa considerar esse root existente; não instalar a imagem
experimental nem remover Magisk nesta etapa.

## Comparar a imagem enviada com o boot instalado

A imagem `boot[1].img` enviada contém o mesmo kernel da referência oficial Google,
mas ainda falta comparar a imagem completa com a partição ativa do aparelho.

1. Baixe `conferir-boot.cmd` e coloque-o na pasta com `adb.exe`.
2. Conecte somente o Moto G75, com Android iniciado e depuração USB autorizada.
3. Abra o script e autorize **Shell** se o Magisk solicitar acesso root.
4. Envie `conferencia-boot.txt` da pasta `conferencia-boot-...` criada ao lado do script.

Esse script verifica o SKU XT2437-1, consulta firmware e slot e usa `su` somente
para executar `id` e `sha256sum` sobre `boot_a` e `boot_b`. Não grava partições,
reinicia o aparelho ou instala/remove root. Os dois slots são lidos para que a
análise não dependa de presumir que o slot ainda é `a`. Uma falha de acesso não
significa que a imagem seja incompatível. O script foi revisado estaticamente;
sua execução em Windows depende da coleta pelo proprietário.

## Copiar o estado atual do slot a

**Resultado recebido:** `boot-atual-a.img` já foi copiado e seu hash confere com o
mostrado no telefone. Ele contém o kernel Google original e um ramdisk Magisk.
Não é necessário repetir essa cópia. Para identificar qual dos arquivos de
`init_boot` recebidos corresponde ao instalado, basta esta leitura no mesmo CMD:

```cmd
adb.exe shell "su -c 'sha256sum /dev/block/by-name/init_boot_a'"
```

Envie o resultado. Se ele corresponder a uma cópia já recebida, não será preciso
transferir o `init_boot` novamente. Os comandos abaixo ficam como referência de
backup, não como solicitação para repetir os arquivos já conferidos.

O terminal fotografado pelo proprietário é **cmd.exe**, o slot observado é `_a` e
a leitura root foi autorizada no Magisk. Nesse terminal, dentro de `platform-tools`,
os comandos abaixo copiam as duas partições para arquivos no computador:

```cmd
adb.exe exec-out "su -c 'cat /dev/block/by-name/boot_a'" > boot-atual-a.img
adb.exe exec-out "su -c 'cat /dev/block/by-name/init_boot_a'" > init-boot-atual-a.img
```

Execute uma linha por vez e aguarde o prompt retornar. O redirecionamento binário
acima é para **cmd.exe**; não usar esse procedimento em Windows PowerShell 5.
Use somente com o slot `_a` confirmado e nomes de saída ainda não usados, pois o
redirecionamento substitui arquivos existentes com esses nomes. Não há gravação
nas partições do telefone. As cópias representam o estado atual; `init_boot` pode
estar modificado pelo Magisk. Depois da transferência, os hashes devem ser
conferidos antes de tratar essas cópias como utilizáveis para recuperação.

## Coleta após a conferência do init_boot e dos caminhos dos módulos

A foto posterior mostrou que o hash de `init_boot_a` difere das duas imagens já
recebidas. Também confirmou os diretórios reais dos módulos. Com o mesmo aparelho
no slot `a`, execute no **cmd.exe**, na pasta `platform-tools`, uma linha por vez:

```cmd
adb.exe exec-out "su -c 'cat /dev/block/by-name/init_boot_a'" > init-boot-atual-a.img
adb.exe exec-out "su -c 'toybox tar -czf - -C / system_dlkm/lib/modules vendor_dlkm/lib/modules'" > modulos-g75.tar.gz
adb.exe exec-out "su -c 'cat /dev/block/by-name/vendor_boot_a'" > vendor-boot-atual-a.img
```

Espere o prompt retornar após cada linha. Os arquivos são gravados no computador;
as partições e os módulos do telefone são somente lidos. Não reutilize nomes que
identifiquem backups anteriores que ainda deseja guardar. O primeiro arquivo
permite conferir o estado atual do init_boot; o segundo contém módulos e suas
listas de carregamento; vendor_boot permite examinar o ramdisk e eventuais módulos
usados no início da inicialização. Envie os três arquivos na conversa. Não é
necessário repetir `boot-atual-a.img`, que já foi conferido.

O `tar` usa caminhos relativos à raiz para não gerar avisos sobre a remoção da
barra inicial. As opções de criação, gzip e diretório constam da
[ajuda oficial do Toybox no Android](https://android.googlesource.com/platform/external/toybox/+/988e2e2ba7c9a7540de39bb77185f20c83da8eb6/android/device/generated/help.h).
A sintaxe foi revisada; a execução e a integridade dos arquivos coletados ainda
dependem da transferência pelo proprietário. Se houver erro, envie a mensagem.

## Conferir estado do bootloader

Estes comandos reiniciam para o bootloader, consultam duas variáveis e retornam ao
Android. Execute-os no terminal do Windows aberto na pasta `platform-tools`, com
somente o Moto G75 conectado. Termine o que estiver fazendo no telefone antes de
reiniciar.

```powershell
.\adb.exe reboot bootloader
```

Quando a tela do bootloader aparecer, execute:

```powershell
.\fastboot.exe getvar unlocked
.\fastboot.exe getvar securestate
```

Copie as respostas dessas duas consultas para a conversa. Se alguma variável não
for suportada, envie também a mensagem de erro; isso não confirma bloqueio. Se
aparecer `waiting for any device`, interrompa com Ctrl+C e informe o problema de
conexão. Para retornar ao Android, use:

```powershell
.\fastboot.exe reboot
```

`getvar` consulta informações. Não use comandos `flashing lock`, `flashing unlock`,
`oem unlock`, `flash` ou `erase` para essa verificação. O campo `secure` isolado não
equivale ao estado de desbloqueio.
