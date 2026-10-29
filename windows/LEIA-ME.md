# Diagnóstico pelo Windows

O proprietário confirmou sistema original Motorola com **Magisk** e acesso a um
computador Windows. A coleta confirmou SKU **XT2437-1**, slot **a**, páginas de 4096
bytes e configuração do kernel idêntica à referência Google. A versão do Magisk
ainda não foi coletada. O estado de bootloader informado por `getprop` foi `locked`,
em divergência com o relato do proprietário; a consulta abaixo permite conferir
diretamente no fastboot.

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
