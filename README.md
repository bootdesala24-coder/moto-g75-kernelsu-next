# Moto G75 — laboratório de compilação KernelSU Next

Este projeto compila uma referência GKI e um kernel com KernelSU Next v3.4.2
integrado. A compilação e as verificações estáticas passaram. Foi preparado um
pacote candidato para o **XT2437-1, W1UQ36H.73-38, retbr, slot a**, com boot sem
Magisk, init_boot sem patch, Manager oficial e cópias para restauração.
**Ainda não houve teste físico no aparelho. Não há garantia de inicialização ou
de segurança de 100%.** As imagens e os backups pessoais não são publicados neste
repositório; os scripts, hashes e relatórios permitem revisar a preparação.

## Pacote candidato preparado

A execução [40807792629](https://github.com/bootdesala24-coder/moto-g75-kernelsu-next/actions/runs/40807792629)
passou nos quatro jobs. A comparação manteve os mesmos 9.110 símbolos exportados,
com `CONFIG_KSU` como única diferença de configuração entre as duas variantes.
O certificado público original está na lista confiável de ambos os kernels;
as tabelas de proteção coincidem com as do kernel instalado.

O artefato KernelSU também passou na comparação dos **3.407 requisitos do núcleo
extraídos dos módulos reais do proprietário**. A imagem `boot-kernelsu-next.img`
tem SHA-256 `c7e9d4f752a804c81107cb1c057fa7f5f8abec3a7bd2a5e98fe682575bf07160`.
Ela preserva os campos do cabeçalho original, salvo o tamanho do novo kernel,
usa kernel sem compressão e ramdisk vazio. O hash AVB foi recalculado e conferido
com algoritmo `NONE`; isso não é uma assinatura OEM.

O pacote inclui a base init_boot cujo conteúdo foi relacionado ao backup interno
do Magisk instalado, o Manager oficial com assinatura APK v2 e certificado
conferidos contra a identidade esperada pelo kernel, e os backups atuais do
boot/init_boot. O procedimento guarda módulos e scripts Magisk em uma pasta
separada, sem apagá-los. A preparação e a restauração foram simuladas em diretórios
temporários, inclusive recusa de modelo errado, repetição e sobrescrita de dados.
A execução em Windows e no telefone continua dependente do teste do proprietário.

Veja [validação do pacote](docs/packaged-kernel-validation.json),
[manifesto da entrega](docs/delivery-package.json),
[comparação do Actions](docs/ci-comparison-40807792629.json) e
[instruções de migração e retorno](windows/LEIA-ME-PACOTE.txt).
`analysis/package_boot.py` recusa insumos com hashes inesperados e repete os checks
antes de empacotar; `analysis/finalize_package.py` monta e verifica o ZIP.

## Resultado da compilação experimental

A execução [40796422378](https://github.com/bootdesala24-coder/moto-g75-kernelsu-next/actions/runs/40796422378),
no commit `476ab8948c9e664fd9d11cdea6e762ccd039e0a5`, concluiu com sucesso os jobs de
verificação, referência, KernelSU Next e comparação. Foram comparados **9.110 símbolos**
exportados em cada variante, sem adições, remoções ou mudanças de CRC, classe ou
namespace. A única diferença de configuração entre as duas variantes foi `CONFIG_KSU`.
O [relatório preservado](docs/ci-comparison-40796422378.json) reproduz os dados do job.

Esse resultado compara duas compilações do projeto. A análise posterior confirmou
que o kernel extraído do `boot_a` instalado é idêntico à referência oficial Google.
A análise dos módulos reais, recebidos posteriormente, está descrita abaixo. A primeira compilação não
continha o certificado público original de assinatura dos módulos; a correção
descrita abaixo foi concluída na execução 40807792629. O pacote atual permanece
um candidato a teste físico, sem validação de inicialização no aparelho.

### Preservação da confiança nos módulos

A compilação agora extrai o certificado público do kernel Google conferido por
SHA-256 e o inclui em `CONFIG_SYSTEM_TRUSTED_KEYS`. Não usa nem precisa da chave
privada do Google. `CONFIG_MODULE_SIG_PROTECT`, CFI e as demais proteções verificadas
continuam habilitadas. A chave privada gerada pelo laboratório não é publicada.

O Actions verifica, pelos endereços de `System.map`, que o certificado original está
na lista de certificados confiáveis do `Image` compilado. Também exige igualdade
binária com as tabelas originais de 8.925 símbolos acessíveis a módulos sem assinatura
e 506 símbolos de exportação protegida. Encontrar o certificado em outra parte da
imagem não basta para passar na verificação. Os offsets e hashes de referência estão
fixados em `sources.lock.json`; a análise inicial está em
[`docs/module-trust-inspection.json`](docs/module-trust-inspection.json).

Essas verificações preservam a confiança e as listas de proteção. A análise dos
CRCs, assinaturas e dependências reais foi realizada separadamente, conforme a
seção seguinte; a operação física dos drivers continua pendente.

### Verificação dos módulos reais do aparelho

O proprietário enviou `modulos-g75.tar.gz`, `vendor-boot-atual-a.img` e
`init-boot-atual-a.img`. A análise encontrou **618 arquivos de módulos, correspondentes
a 448 binários únicos**: 96 em system_dlkm, 269 em vendor_dlkm e 253 no ramdisk
de vendor_boot. Os nomes repetidos contêm os mesmos bytes.

Na comparação estática com o artefato KernelSU da primeira execução (40796422378):

- Todos os **96 módulos assinados** tiveram a assinatura criptográfica verificada
  usando exclusivamente o certificado público do kernel original. Controles com
  conteúdo alterado e certificado incorreto foram rejeitados.
- Os **3.407 símbolos do núcleo exigidos pelos módulos** têm CRC correspondente;
  foram conferidos 29.987 registros de importação do núcleo e 3.454 entre módulos.
- Não foram encontrados símbolos exigidos sem provedor, CRCs divergentes,
  violações das listas de proteção, namespaces não declarados ou uso incompatível
  de exports GPL nos arquivos analisados. Todos possuem tabela `__versions` e
  `module_layout=0x4e276f37`.
- As três variantes de vermagic possuem o mesmo sufixo de configuração. A fonte
  fixada compara esse sufixo quando o módulo possui CRCs; a diferença do nome da
  versão não foi contornada por carregamento forçado.
- Todas as 3.425 referências de caminhos em `modules.dep` têm arquivo correspondente.
  As 64 dependências entre estágios ausentes dos respectivos grafos locais são
  fornecidas por módulos da lista de carregamento inicial. As listas normal e de
  recuperação, com suas dependências, estão cobertas pelos arquivos do vendor_boot.

Isso ainda **não valida o carregamento real nem o comportamento dos drivers**.
A primeira compilação não contém o certificado original no keyring, por isso esse
resultado de CRC não a torna adequada para instalação. A execução
[40807792629](https://github.com/bootdesala24-coder/moto-g75-kernelsu-next/actions/runs/40807792629)
concluiu a correção e a comparação posterior dos módulos passou. As tabelas
Module.symvers das compilações anterior e corrigida são idênticas byte a byte;
a correção acrescenta a confiança no certificado original.

O [relatório](docs/device-module-validation.json), o
[manifesto de arquivos](docs/device-module-manifest.json) e os
[requisitos extraídos](docs/device-module-requirements.json) permitem revisar a análise
sem publicar os binários do telefone. Para repetir a comparação do núcleo:

```sh
python3 analysis/verify_device_modules.py --build-dir CAMINHO_DO_ARTEFATO
python3 -m unittest discover -s analysis -p 'test_*.py' -v
```

`analysis/inspect_modules.py` permite repetir a inspeção ELF, assinaturas e
comparação completa com as cópias locais dos módulos; consulte `--help`.

### Imagem de boot recebida

A análise de `boot[1].img` encontrou uma imagem Android v4 de 96 MiB, kernel sem
compressão e ramdisk vazio. O kernel é idêntico byte a byte à referência Google
fixada em `sources.lock.json`; a configuração embutida coincide com a coletada no
telefone. O hash AVB interno da imagem completa também confere. O
[relatório de inspeção](docs/boot-image-inspection.json) registra tamanhos, hashes e
metadados; nenhum arquivo binário do proprietário foi publicado no repositório.

O VBMeta externo usa algoritmo `NONE`: conferir esse hash não autentica a origem
Motorola nem substitui verificar a cadeia AVB do firmware. Seus metadados indicam
`motorola/paros/paros:15/VUQ35HV-W1-ST28/ac0a9:user/release-keys`, diferente do
fingerprint Android 16 coletado do sistema. Isso não basta para concluir que o boot
seja incompatível; a imagem completa precisa ser comparada com a partição ativa.
O script [`windows/conferir-boot.cmd`](windows/conferir-boot.cmd) coleta os hashes
por leitura usando o Magisk já instalado.

A coleta posterior, fotografada pelo proprietário após autorizar Shell no Magisk,
mostra o mesmo SHA-256 para `boot_a` e `boot_b`, começando por `55c2ccec`. Esse hash
difere do arquivo enviado, que começa por `6ae39d54`. O slot exibido continua sendo
`_a`.

A cópia posterior `boot-atual-a.img` tem 96 MiB e SHA-256
`55c2ccece3ef93e0daba10a8b8a9332f83d3dcf6437cfaa973678851776c4c71`,
exatamente o valor fotografado no telefone. Seu kernel é idêntico byte a byte ao
kernel do boot anterior e à referência Google. A diferença inclui um ramdisk Magisk
de 360.841 bytes, onde o boot anterior tinha ramdisk vazio. O `SHA1` guardado pelo
Magisk nesse ramdisk coincide com o hash completo do `boot[1].img` fornecido.

Isso identifica uma cópia fiel do boot atual e sua relação com a base anterior ao
patch. Não determina quando ou como o patch em `boot` foi aplicado. O relato de
patch em `init_boot` também está documentado e o arquivo correspondente foi
analisado. O relatório do
boot atual está em [`docs/current-boot-image-inspection.json`](docs/current-boot-image-inspection.json).

A consulta posterior de `init_boot_a`, fotografada pelo proprietário, retorna um
SHA-256 iniciado por `eaaa88a4`, diferente tanto da cópia sem patch (`7746e1b3...`)
quanto da cópia Magisk recebida (`75cfea5d...`). Portanto, nenhuma delas foi
confirmada como backup do estado atual de `init_boot_a`; é necessário receber a
cópia instalada para análise. A mesma foto confirma `/system/lib/modules` como
link para `/system_dlkm/lib/modules` e `/vendor/lib/modules` como link para
`/vendor_dlkm/lib/modules`. Os dados foram registrados em `docs/device-observations.json`.

### Imagem de init_boot recebida novamente

O proprietário reiterou que aplicou o patch do Magisk em **init_boot**. O arquivo
reenviado, `init_boot[1](1).img`, tem 8 MiB, cabeçalho v4, nenhum kernel e um ramdisk
LZ4 legacy de 2.455.247 bytes. O hash AVB interno confere. O ramdisk foi descompactado
e seu CPIO analisado; não contém os marcadores comuns `magisk`, `.backup/.magisk`,
`.backup/init` ou `overlay.d/sbin`. Isso é compatível com uma cópia anterior ao
patch, mas não autentica o arquivo como original nem confirma a versão instalada.

O `build.prop` do ramdisk identifica `VUQ35HV-W1-ST28`, Android 15, em concordância
com os metadados do boot candidato. A cópia atual de `boot_a` já foi conferida.
O próximo passo para `init_boot_a` é comparar seu SHA-256 com os arquivos recebidos;
uma nova cópia só é necessária se nenhum corresponder ao conteúdo instalado.
Os detalhes estão no [relatório do init_boot](docs/init-boot-image-inspection.json).

A cópia atual foi recebida e seu SHA-256 `eaaa88a4...` confere com a foto do
telefone. Ela contém Magisk e difere do patch antigo nos executáveis e na ausência
de `stub.xz`. O registro original SHA-1 continua apontando para o mesmo init_boot
sem patch; restaurar o `init` do backup e excluir as entradas Magisk reproduz os
nomes, modos e conteúdos das 17 entradas originais. A versão do Magisk não foi
inferida pelo nome do arquivo. Veja o
[relatório atual](docs/current-init-boot-inspection.json).

O [vendor_boot recebido](docs/current-vendor-boot-inspection.json) possui cabeçalho
v4, páginas de 4096 bytes, um fragmento de ramdisk, DTB e bootconfig. Seu hash AVB
interno confere, mas o algoritmo `NONE` não autentica a origem OEM. Ele foi apenas
inspecionado; nenhum de seus módulos, DTB ou parâmetros foi modificado.

O arquivo `magisk_patched-30700_flRoZ[1].img` também foi analisado. O campo `SHA1`
em `.backup/.magisk` coincide com o hash do init_boot original fornecido. O conteúdo
descompactado de `.backup/init.xz` é idêntico ao `init` original; restaurar esse
arquivo e excluir as entradas adicionadas pelo Magisk reproduz os nomes, modos e
conteúdos de todas as 17 entradas do ramdisk original. Isso confirma a relação entre
os dois arquivos fornecidos, mas ainda não sua igualdade com a partição instalada
hoje. O hash AVB retido no patcheado é o do original e não confere com o conteúdo
modificado; ele não é usado como prova de integridade da imagem patcheada. Veja o
[relatório do patch Magisk](docs/magisk-patched-init-boot-inspection.json).

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
| Bootloader | Foto da inicialização mostra “The boot loader is unlocked”; getprop retorna locked |

A foto enviada depois da coleta confirma o aviso de bootloader desbloqueado na
inicialização. A opção **Desbloqueio de OEM** aparece desligada nas configurações;
essa opção controla a permissão para desbloquear e não bloqueia novamente um
bootloader já desbloqueado. A causa do valor `locked` dentro do Android ainda não
foi determinada. Não foi realizada consulta direta por fastboot.

O `kernel-config.gz` enviado pelo proprietário foi descompactado e comparado byte a
byte com a configuração da referência oficial: são idênticos. SHA-256 da configuração
descompactada: `4bc095f8fb1b94d9841393ae949492f38328d9919f7e99d0853fdf2c989b4719`.
Isso confirma a configuração de entrada. A cópia posterior de `boot_a` confirmou
também igualdade binária do kernel instalado com a referência Google. A compatibilidade
da recompilação com os módulos ainda não foi estabelecida. Os dados coletados estão
em [`docs/device-observations.json`](docs/device-observations.json), e `device.json`
foi atualizado para a próxima compilação; os artefatos antigos preservam suas entradas.

## Fontes e limites da primeira compilação

- AOSP/Google: `kernel/common`, tag `android15-6.6-2025-05_r19`, commit
  `88d70c0b44bff103947b599e40bb36bd5af92891`.
- A tag oficial aponta para o build **14541233**. O prefixo do commit e esse build ID
  coincidem com `g88d70c0b44bf-ab14541233` na foto do telefone. A fonte é Linux 6.6.87,
  KMI 8. O kernel instalado coincide byte a byte com a referência Google desse build.
  Isso não comprova que uma recompilação será instalável.
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
- O certificado público original será incorporado à lista de confiança da nova
  compilação, junto ao certificado do laboratório. A aceitação dos módulos reais
  do aparelho passou nos checks estáticos documentados; o carregamento real
  ainda precisa ser testado.
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
7. Certificado público original na lista confiável e tabelas de proteção idênticas
   às do kernel original, conferidos dentro de cada `Image` compilado.

Essa comparação **não** é uma análise ABI completa nem uma comparação com os módulos
binários da Motorola. Os módulos são compilados para diagnóstico, mas não são
empacotados para substituição de `vendor_dlkm` ou `system_dlkm`.

Os artefatos incluem imagens brutas, `.config` como `kernel.config`, `Module.symvers`,
`System.map`, certificado público original, cabeçalhos das tabelas de proteção,
logs, origem dos insumos, versões dos pacotes e `SHA256SUMS`.
O nome do kernel contém `lab` para identificar o experimento. Os arquivos ficam no
Actions por 14 dias. O workflow entrega kernels brutos e diagnósticos. O pacote
com boot, init_boot e instruções é preparado separadamente pelos scripts em
`analysis/`, após verificar os artefatos e as imagens do proprietário. Não há
release pública automática nem validação física implícita.

## Pendências para uma eventual instalação

- Desbloqueio observado no aviso de inicialização; SKU XT, tamanho de página e slot
  coletados; sistema Motorola e Magisk relatados. Não refazer o desbloqueio nem
  bloquear novamente para tentar corrigir a propriedade divergente no Android.
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
