# Diagnóstico pelo Windows

O proprietário confirmou sistema original Motorola com **Magisk** e acesso a um
computador Windows. A versão do Magisk, o SKU XT e o slot ativo ainda não foram
coletados. As fotos e esses relatos não substituem a leitura dos arquivos reais.

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
