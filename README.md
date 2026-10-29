# Moto G75 — laboratório de compilação KernelSU Next

Este projeto compila duas imagens **experimentais**: uma referência GKI sem root e
outra com KernelSU Next v3.4.2 integrado. Não é um pacote de instalação e ainda não
há validação no aparelho. Um workflow verde não significa que o kernel seja seguro
para instalar, que inicialize no Moto G75 ou que seja idêntico ao kernel original.

## Aparelho identificado

| Campo | Valor observado |
|---|---|
| Modelo | moto g75 5G; XT2437-1; codinome sorap |
| Firmware | W1UQ36H.73-38 |
| Sistema/canal | Android 16 / retbr |
| Patch Android | 2026-04-01 |
| Kernel | 6.6.87-android15-8-g88d70c0b44bf-ab14541233-4k |
| KMI | android15-6.6, geração 8 |
| Páginas | 4096 bytes, confirmado por getconf |
| Slot observado | a |
| SELinux observado | Enforcing |
| Root existente | Magisk, informado pelo proprietário |
| Bootloader | Proprietário informa desbloqueado; getprop retorna locked; falta conferir no fastboot |

O `kernel-config.gz` enviado pelo proprietário foi descompactado e comparado byte a
byte com a configuração da referência oficial: são idênticos. SHA-256 da configuração
descompactada: `4bc095f8fb1b94d9841393ae949492f38328d9919f7e99d0853fdf2c989b4719`.
Isso confirma a configuração de entrada; não confirma equivalência binária do kernel
nem compatibilidade dos módulos. Os dados coletados estão em
[`docs/device-observations.json`](docs/device-observations.json). O `device.json`
preserva as entradas da primeira compilação, anterior ao recebimento da coleta.

## Fontes e limites da primeira compilação

- AOSP/Google: `kernel/common`, tag `android15-6.6-2025-05_r19`, commit
  `88d70c0b44bff103947b599e40bb36bd5af92891`.
- A tag oficial aponta para o build **14541233**. O prefixo do commit e esse build ID
  coincidem com `g88d70c0b44bf-ab14541233` na foto do telefone. A fonte é Linux 6.6.87,
  KMI 8. A equivalência binária, os módulos OEM e as imagens de boot ainda não foram
  verificados. Isso não comprova que uma recompilação será instalável.
- KernelSU Next: tag `v3.4.2`, commit
  `4c706b5938665866ebe16944a481a7b91e3396af`. Manager padrão da mesma release.
- Android Clang `r510928`, conforme o `build.config.constants` dessa tag AOSP.
  O conteúdo extraído é conferido pelo hash da árvore Git original antes de executar
  o compilador. Todos os identificadores estão em `sources.lock.json`.
- Configuração extraída da imagem certificada publicada pelo Google para o build
  14541233. ZIP, kernel e configuração têm hashes SHA-256 fixados. Essa referência
  usa `CONFIG_LTO_NONE=y` com CFI habilitado; esses valores são preservados.
- Compilação direta via Kbuild. O ambiente Kleaf hermético não é reproduzido;
  `abi_symbollist.raw` é gerado pela união das listas arm64 da fonte fixada. O
  relatório registra diferenças da configuração oficial. A imagem Google é apenas
  uma referência técnica, não um backup do boot Motorola.
- As chaves de assinatura de módulos geradas nesta compilação não são as chaves
  privadas do Google. A aceitação dos módulos existentes, inclusive os protegidos,
  ainda precisa ser verificada antes de qualquer instalação.
- Não inclui SUSFS adicional, overclock, alterações térmicas, desativação de SELinux,
  alteração da assinatura autorizada do Manager ou autorização automática de root.

## GitHub Actions

O workflow `.github/workflows/build.yml` inicia após mudanças em `main` nos arquivos
de compilação, ou pelo botão **Actions → Experimental GKI 6.6.87 and KernelSU Next →
Run workflow**. Não há agendamento. A matriz executa dois jobs e cada um tem limite
de 150 minutos. As permissões são somente leitura; nenhum segredo é necessário.

Os jobs verificam entradas, compilam `Image`, imagens comprimidas e módulos e conferem:

1. Commit de origem, versão do kernel, compilador e geração KMI.
2. Configuração arm64/4 KB, CFI, modo LTO da referência, MODVERSIONS e proteções selecionadas.
3. Presença de KernelSU integrado apenas na variante correspondente, sem debug.
4. Cabeçalho, tamanho e arquitetura do `Image`.
5. CRC, classe e namespace dos símbolos exportados, comparando as duas compilações.
6. Diferenças de configuração inesperadas entre referência e KernelSU.

Essa comparação **não** é uma análise ABI completa nem uma comparação com os módulos
binários da Motorola. Os módulos são compilados para diagnóstico, mas não são
empacotados para substituição de `vendor_dlkm` ou `system_dlkm`.

Os artefatos incluem imagens brutas, `.config` como `kernel.config`, `Module.symvers`,
`System.map`, logs, origem dos insumos, versões dos pacotes e `SHA256SUMS`.
O nome do kernel contém `lab` para identificar o experimento. Os arquivos ficam no
Actions por 14 dias. Não são produzidos `boot.img`, `init_boot.img`, ZIP AnyKernel ou
comandos de flash. Não há release automática nem indicação de instalação.

## Pendências para uma eventual instalação

- Resolver a divergência de estado do bootloader por consulta no fastboot. SKU XT,
  tamanho de página e slot foram coletados; sistema Motorola e Magisk foram relatados.
- Obter firmware original **W1UQ36H.73-38 / canal retbr**, com origem verificável,
  e as imagens originais e módulos pertinentes; guardar hashes e cópias de restauração.
- Identificar layout de boot, slot ativo, cabeçalhos, compactação e AVB/rollback a
  partir dos arquivos reais. Não pressupor que se deve gravar `boot` ou `init_boot`.
- Confirmar ABI/configuração contra os módulos do aparelho e reproduzir a base adequada.
- Preparar recuperação específica antes do primeiro teste de inicialização.
- Validar no aparelho inicialização, root, SELinux, rede móvel, Wi-Fi, Bluetooth, GPS,
  câmeras, áudio, biometria, carregamento, suspensão, temperatura e reinicializações.

Para o objetivo de obter root, o modo LKM do KernelSU Next também merece avaliação:
ele pode preservar o kernel original, se as verificações de compatibilidade permitirem.
Isso não foi instalado ou testado neste aparelho.

## Validação local dos scripts

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --inputs
```

Fontes: [Tag AOSP e build 14541233](https://android.googlesource.com/kernel/common/+/refs/tags/android15-6.6-2025-05_r19),
[KernelSU Next v3.4.2](https://github.com/KernelSU-Next/KernelSU-Next/releases/tag/v3.4.2),
[Clang fixado](https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+/a88a49e4f9d0ad9562e3dd75a3c197689d1a63f3/clang-r510928/).
