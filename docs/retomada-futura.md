# Retomar a compilação do Moto G75

Registro de 29/10/2026, fuso America/Fortaleza. Este documento é a entrada atual
para continuar o projeto. Leia junto com `user-confirmed-success.json`.

## O que aconteceu

O proprietário confirmou na conversa: “deu totalmente certo chatgpt!!!”, após
receber o pacote KernelSU Next v3.4.2. O resultado foi informado pelo usuário;
não houve coleta de logs após a instalação nem confirmação separada de cada
driver, do método de instalação usado ou de estabilidade prolongada.

O objetivo é manter KernelSU Next integrado ao kernel (CONFIG_KSU=y), substituindo
o Magisk. O proprietário relatou ter instalado o Magisk originalmente por
`init_boot`. As imagens atuais coletadas antes da migração tinham componentes
Magisk tanto em boot quanto em init_boot. Isso não permite inferir quando ou como
o boot foi alterado. O pacote contemplou as duas partições.

Não pedir novamente os arquivos ou capturas já preservados apenas para recompilar
a mesma base. Para uma atualização futura, verificar se o aparelho mudou desde
este registro. Novos dados só são necessários para mudanças ou lacunas reais.

## Identidade e base conhecida

| Campo | Valor |
|---|---|
| Modelo/SKU | moto g75 5G / XT2437-1 |
| Codinome / plataforma | sorap / parrot |
| Firmware / canal | W1UQ36H.73-38 / retbr |
| Android / patch | 16 / 2026-04-01 |
| Fingerprint do sistema | motorola/paros_g/sorap:16/W1UQ36H.73-38/ac0a9-1e98c:user/release-keys |
| Kernel original | 6.6.87-android15-8-g88d70c0b44bf-ab14541233-4k |
| Kernel entregue | 6.6.87-android15-8-lab-4k |
| KMI / página | android15-6.6-8 / 4096 bytes |
| Slot observado antes da migração | a; conferir novamente no futuro |
| SELinux observado antes da migração | Enforcing |
| Bootloader | Desbloqueado segundo relato e aviso fotografado; não relockar |
| Root entregue | KernelSU Next v3.4.2, versão 33355, Manager padrão |

Há metadados Android 15 / VUQ35HV-W1-ST28 nas imagens de boot, mesmo com o sistema
Android 16. Eles também estavam nas imagens que o telefone usava. Foram
preservados; não os “corrigir” apenas pelo número do Android.

## Atualizar o aplicativo não é sempre recompilar

O Manager é um aplicativo. A parte CONFIG_KSU=y está integrada ao kernel. Uma
atualização compatível só do Manager pode dispensar nova compilação. Atualizar a
parte integrada requer recompilar e instalar uma nova imagem de boot. Verificar
as notas oficiais, a versão mínima aceita, a interface UAPI e a assinatura do
Manager; atualizar só o APK não atualiza o código já integrado ao kernel.

Não presumir que toda release obriga uma atualização imediata, nem que um novo
Manager continuará compatível. Não confundir este projeto integrado com as
instruções de instalação LKM ou com o projeto KernelSU original.

Se o Android/firmware Motorola, a base do kernel, os módulos, o layout ou a geração
KMI mudarem, tratar como nova análise. Uma OTA pode mudar o slot ativo. Não gravar
o boot antigo sobre o firmware novo por semelhança de nome.

## Referências que precisam ser preservadas

- Repositório: https://github.com/bootdesala24-coder/moto-g75-kernelsu-next
- Execução válida: https://github.com/bootdesala24-coder/moto-g75-kernelsu-next/actions/runs/40807792629
- Commit da compilação válida: `4f35aa7973b574d63593624d988cfbe4764f0078`.
- Commit da receita da entrega: `7c5e4c844e847392b88d55e2a26f75b553aff380`.
- Fonte AOSP: tag `android15-6.6-2025-05_r19`, commit
  `88d70c0b44bff103947b599e40bb36bd5af92891`, build Google `14541233`.
- KernelSU Next: `v3.4.2`, commit `4c706b5938665866ebe16944a481a7b91e3396af`.
- Clang: `r510928`, commit `a88a49e4f9d0ad9562e3dd75a3c197689d1a63f3`, árvore
  `5c8ecb6fa0e54db3b116ac04e4689e46c3f6eb19`.
- As URLs e hashes completos estão em `sources.lock.json`.

O Actions retém os artefatos por 14 dias. A pasta de continuidade contém cópias
dos dois artefatos completos da execução válida e do pacote original, para não
depender dessa retenção. Ela também contém uma cópia do projeto e um Git bundle.
O código completo do Linux e o compilador são obtidos das fontes fixadas durante
a compilação; não estão integralmente incluídos na pasta. Portanto, ela não é um
ambiente de compilação totalmente offline.

Não prometer reprodução byte a byte: a receita gera uma chave de laboratório
e utiliza pacotes do runner. O ambiente hermético Kleaf não foi reproduzido.
Os hashes preservados autenticam a integridade dos arquivos guardados, não uma
assinatura da Motorola nem uma garantia de futuras compilações.

## Por que esta compilação funcionou nos checks

O kernel original foi comparado byte a byte com a referência oficial Google.
A configuração coletada no telefone também coincide com essa referência.
Preservamos 4K, CFI, MODVERSIONS, LTO_NONE, SELinux e as proteções de módulos.
O kernel usa CONFIG_KSU=y, sem debug, sem SUSFS adicional e sem mudanças térmicas
ou overclock. O Manager é a variante padrão, sem alteração da assinatura esperada.

O certificado público original de assinatura de módulos precisa permanecer
**dentro do builtin trusted keyring**, não apenas em algum lugar do Image. A
primeira execução, 40796422378, não tinha esse requisito corrigido; não usá-la
como imagem de instalação. A execução 40807792629 corrigiu isso e passou.

Também foram preservadas as tabelas originais de 8.925 símbolos acessíveis a
módulos não assinados e 506 exports protegidos, conferidas por conteúdo, tamanho
e posição no Image. São verificações necessárias; não desligar as proteções para
fazer um teste passar. Os headers gerados ficam em `out/include/generated/`.

Nos quatro jobs aprovados, referência e KernelSU têm os mesmos 9.110 símbolos
exportados, sem alterações de CRC/classe/namespace. CONFIG_KSU foi a única
diferença de configuração entre as duas variantes.

Foram inspecionados 618 arquivos de módulos do aparelho (448 binários únicos),
com 3.407 requisitos de símbolos do núcleo. Todos passaram nas verificações
estáticas documentadas. Os 96 módulos assinados foram verificados usando o
certificado original. Módulos vendor sem assinatura não foram tratados como
inválidos automaticamente: vale a política original GKI. Ver `docs/device-module-*`.
Isso não substitui testar o comportamento real dos componentes.

## Como preparar uma versão futura na mesma base

1. Preservar o pacote funcional v3.4.2. Coletar somente o estado atual necessário:
   firmware, versão do kernel, slot, estado do root e hashes das partições ativas.
   Não pressupor que `_a` ainda é o slot ativo. Se houve OTA, reanalisar a base.
2. Conferir a release oficial desejada e seu commit. Criar uma branch de trabalho,
   mantendo a receita funcional intacta. Atualizar tag e commit em
   `sources.lock.json`; nunca usar uma branch móvel como identidade de entrega.
3. Examinar mudanças na integração, Kconfig, versão/UAPI e identidade do Manager.
   `scripts/build.py` clona KernelSU com histórico completo, confere a tag, integra
   `drivers/kernelsu`, habilita KSU e valida o resultado. Não reduzir o clone sem
   conferir como a nova release calcula a versão. Revisar opções novas e seus
   efeitos; não desativar checks para aceitar um diff desconhecido.
4. Na mesma base, manter AOSP, Clang, referência, whitelist, certificados e formato
   das imagens. Mudar o Linux só quando houver motivo e nova validação. Executar
   `python3 -m unittest discover -s tests -v`,
   `python3 -m unittest discover -s analysis -p 'test_*.py' -v` e
   `python3 scripts/validate.py --inputs`.
5. Executar o workflow na branch atualizada pelo botão Run workflow. Ele não tem
   um campo de versão: rodar main sem mudar os pins recompila a mesma versão.
   Os quatro jobs precisam terminar com sucesso: checks, reference,
   kernelsu-next e compare. O job de build tem limite de 150 minutos por variante.
   GitHub Actions entrega kernels brutos, não um novo boot pronto para flash.
6. Baixar os dois artefatos e conferir seus hashes e SHA256SUMS internos. Repetir a
   comparação, o keyring e as tabelas de proteção. Executar
   `python3 analysis/verify_device_modules.py --build-dir CAMINHO_DO_ARTEFATO`.
   Os requisitos guardados só valem para os módulos inspecionados desta base.
7. Obter o APK oficial correspondente. Verificar hash, assinatura APK, certificado
   e identidade esperada pelo kernel. Não assumir que a assinatura da nova
   versão é a mesma sem conferir. Não publicar ou pedir chaves privadas.
8. Adaptar o empacotamento conscientemente. `analysis/package_boot.py` e
   `analysis/finalize_package.py` estão fixados na entrega v3.4.2: têm hashes,
   nome de APK, partições e backups Magisk específicos. Não são uma atualização
   universal. Atualizar entradas, nomes, relatórios e testes ao preparar uma nova
   versão; não simplesmente remover o dicionário EXPECTED.
9. Para a mesma base, preservar header v4, tamanho de partição 96 MiB, kernel raw
   sem compressão e ramdisk de boot vazio. Recalcular e verificar o hash AVB com
   algoritmo NONE. Isso não gera assinatura OEM. O init_boot já está sem Magisk;
   uma atualização só do kernel normalmente não requer gravá-lo novamente.
10. O rollback futuro principal deve ser a versão KernelSU que já funciona.
    Backups Magisk são históricos. Não repetir `preparar-migracao.sh` nas
    atualizações: foi feito para a primeira migração e move diretórios de módulos.
    Não rodar a opção de desinstalação/restauração de imagens do Magisk após
    instalar o novo kernel. Não misturar pacotes nem gravar slot inativo por palpite.
11. Validar os novos comandos de instalação contra o slot e firmware atuais e
    preparar retorno antes do teste. O suporte deste Moto G75 a `fastboot boot`
    não foi confirmado separadamente. Usar apenas se suportado; falha desse
    comando não prova incompatibilidade do kernel nem autoriza prosseguir.
12. Após instalar, documentar boot, root, SELinux, Wi-Fi, rede móvel, Bluetooth,
    GPS, câmeras, áudio, biometria, carga, suspensão, temperatura e reinícios.
    Registrar versão, hashes, commit, execução, testes e resultado. Guardar um
    pacote novo sem sobrescrever o pacote anterior que funciona.

## Limites e recuperação

Não há comando de flash automático nesta pasta de continuidade. O guia antigo
de migração é histórico e foi preparado para W1UQ36H.73-38 / slot a. Não o aplicar
automaticamente depois de OTA. Não relockar o bootloader com imagens modificadas,
não apagar dados, não desativar AVB por conveniência e não substituir vendor_boot,
vbmeta ou módulos vendor sem nova necessidade comprovada e validação.

Para voltar de uma futura atualização na mesma base, a imagem de recuperação
preferencial é `boot-kernelsu-next.img` do pacote v3.4.2 que funcionou. O
`init_boot-sem-magisk.img` só deve ser restaurado se houver motivo, for a mesma
base e a partição tiver sido alterada. O pacote inclui backups Magisk anteriores
à migração, mas voltar a eles reintroduz o root antigo. Não confundir esses casos.

Não existe garantia de recuperação em qualquer cenário; perda de acesso ao
bootloader ou alterações de firmware exigem outra análise. Guardar backups dos
dados pessoais separadamente: este arquivo não contém fotos, aplicativos ou uma
imagem completa do armazenamento do usuário.

## Fontes oficiais para consultar novamente no futuro

- Releases: https://github.com/KernelSU-Next/KernelSU-Next/releases
- Integração: https://kernelsu-next.github.io/webpage/pages/installation.html
- Release base: https://github.com/KernelSU-Next/KernelSU-Next/releases/tag/v3.4.2
- AOSP: https://android.googlesource.com/kernel/common
- Módulos GKI: https://source.android.com/docs/core/architecture/kernel/modules
- Platform-tools: https://developer.android.com/tools/releases/platform-tools

Documentação online pode mudar. Este registro descreve o que foi preparado e
relatado em 29/10/2026, não fatos automaticamente válidos no futuro.
