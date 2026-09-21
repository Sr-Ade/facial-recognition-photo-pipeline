# Facial Recognition Photo Tagging Pipeline

Pipeline que identifica automaticamente atletas em fotos de jogos de um clube
esportivo amador, para agilizar a criação de posts/artes de redes sociais que
antes eram montados manualmente, foto por foto.

## O problema

O clube tinha centenas de atletas e milhares de fotos de jogos acumuladas em
pastas do Google Drive (organizadas por categoria/ano, e por campeonato).
Montar uma arte de Instagram exigia alguém abrindo pasta por pasta pra achar
uma boa foto de cada atleta manualmente — processo que não escalava com o
crescimento do clube.

## Arquitetura

```
Google Drive (fotos)
        │
        ▼
AWS Rekognition (coleção de rostos indexados)
        │
        ▼
Reconhecimento em fotos de grupo (multi-rosto, com filtro de ruído)
        │
        ▼
Google Sheets (registro: foto, atleta, campeonato, já usada?)
        │
        ▼
Seleção sem repetição → mensagem formatada para o bot de geração de artes
```

- **Indexação**: cada atleta tem uma foto de referência indexada como vetor
  facial numa coleção do AWS Rekognition.
- **Reconhecimento**: fotos de jogo (com múltiplos jogadores) são varridas
  com `detect_faces`, cada rosto é recortado e comparado individualmente
  contra a coleção (`search_faces_by_image`) — não apenas "o rosto maior da
  foto", que é a abordagem ingênua e insuficiente para fotos de time.
- **Controle de qualidade da referência**: ver estudo de caso abaixo.
- **Rastreamento e não-repetição**: uma planilha registra cada
  atleta+foto reconhecidos, com uma flag de "já usada", pra nunca sugerir a
  mesma combinação duas vezes.

## Estudo de caso: quando o algoritmo "funciona" mas está errado

Depois de indexar os atletas usando a primeira foto disponível de cada
pasta (a maioria fotos de ação de jogo, não retratos), o reconhecimento
começou a produzir um padrão sutil: **o mesmo rosto detectado numa foto de
jogo batia com dois atletas diferentes ao mesmo tempo**, ambos com
confiança acima de 98%.

Investigando a foto de referência usada para um dos dois atletas, a causa
ficou clara: era uma foto de ação com **6 pessoas no quadro**, o atleta em
questão estava de costas para a câmera, e o algoritmo de indexação — que
pega "o rosto de maior destaque da imagem" — havia indexado o rosto de
**outra pessoa da foto**, sem qualquer indicação de erro (a chamada de API
"funcionou" normalmente, sem exceção).

Ou seja: o rosto vinculado ao nome daquele atleta na coleção nunca foi o
dele. Isso só ficou visível quando esse rosto "genérico" coincidentemente
apareceu de novo, numa foto de outro jogo, ao lado do atleta que ele
realmente pertencia.

**Diagnóstico**: construí um script de pontuação de qualidade de foto,
usando os próprios atributos que o Rekognition retorna (`Pose.Yaw/Pitch`
para frontalidade, `Quality.Sharpness/Brightness`, tamanho relativo do
rosto, e uma penalidade quando há 2+ rostos de tamanho parecido na mesma
foto — sinal de ambiguidade). Rodando esse script em todas as fotos
disponíveis da pasta do atleta problemático, a foto originalmente indexada
aparecia entre as **piores** do lote.

**Correção**: reindexar aquele atleta especificamente com a foto
mais bem avaliada resolveu os dois lados do problema — eliminou o falso
positivo (o atleta errado deixou de ser sugerido) e recuperou o
verdadeiro positivo (o atleta certo passou a ser reconhecido em fotos
onde antes dava "sem reconhecimento").

**Lição estrutural**: rodei essa mesma avaliação em lote nos ~100 atletas
já indexados. Corrigir automaticamente todos os casos "a melhor foto
disponível é muito melhor que a atual" **quase introduziu uma regressão**
em outro atleta — a foto "mais bonita" escolhida pelo score de qualidade
continha, na real, o rosto de uma terceira pessoa em destaque. A correção
automática foi revertida para esse caso específico após validação prática
(rodando o reconhecimento de novo numa pasta de fotos reais e comparando
antes/depois).

Isso levou à construção de uma ferramenta de auditoria (`detect_confusions`)
que varre qualquer lote de resultados de reconhecimento e sinaliza
automaticamente quando o mesmo rosto físico bate com 2+ identidades acima
de um limiar — transformando uma investigação manual, feita comparando
CSVs linha a linha, num passo de verificação automático e repetível.

**Conclusão prática**: nenhuma heurística de "qualidade de foto isolada"
substitui verificação com dados reais. O pipeline final trata "qualidade
da foto" como uma sugestão, não uma verdade — toda mudança de referência é
seguida de uma rodada de reconhecimento real + auditoria automática antes
de ser considerada válida. E o design de produto que resultou disso: a
melhor solução não é um algoritmo mais esperto, é permitir que uma foto de
retrato dedicada (curada por um humano) sempre tenha prioridade sobre
qualquer heurística automática.

## Estrutura do código

```
src/
├── config.py                     # configuração via variáveis de ambiente
├── drive_client.py                # autenticação e helpers do Google Drive
├── naming.py                      # geração de IDs seguros a partir de nomes
├── setup_collection.py            # cria a coleção no AWS Rekognition
├── index_athletes.py              # indexa (ou reprocessa falhas de) atletas
├── evaluate_reference_quality.py  # pontua fotos de referência (1 atleta ou lote)
├── reindex_athlete.py             # corrige a referência de 1 atleta ou de um lote
├── recognize_photos.py            # reconhecimento multi-rosto numa pasta de fotos
├── generate_html_report.py        # relatório visual (fotos + matches) em HTML
├── detect_confusions.py           # auditoria: mesmo rosto batendo com 2+ pessoas
├── tracking_sheet.py              # cria/atualiza a planilha de controle
├── select_for_content.py          # sugere fotos sem repetir atleta já usado
└── mark_used.py                   # confirma uso de uma foto (fecha o ciclo)
```

## Configuração

1. `cp .env.example .env` e preencha com seus próprios valores (nenhum
   valor real de exemplo é fornecido — IDs de pasta do Drive, ID da
   coleção AWS, ID da planilha).
2. Coloque suas próprias credenciais OAuth do Google (`credentials.json`)
   e configure suas credenciais da AWS (`aws configure`) — nenhuma delas
   deve ser commitada (ver `.gitignore`).
3. `pip install -r requirements.txt`

## Aviso sobre dados

Este repositório contém apenas código. Nenhum dado real de nenhuma pessoa,
foto, planilha, ou identificador de pasta do clube original está incluído
— tudo que aparecia nos testes reais (nomes, IDs, links de fotos) foi
removido antes da publicação, dado que o sistema opera sobre fotos e dados
pessoais de menores de idade.
