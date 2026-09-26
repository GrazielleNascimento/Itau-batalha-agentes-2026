import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[3]
ALVOS_NOVOS = {"stage-data", "deploy", "teardown"}


def _makefile() -> str:
    return (RAIZ / "Makefile").read_text(encoding="utf-8")


def test_makefile_tem_alvos_de_deploy():
    texto = _makefile()
    declarados = {
        linha.split(":")[0]
        for linha in texto.splitlines()
        if ":" in linha and not linha.startswith(("\t", "#", ".", " "))
    }
    assert ALVOS_NOVOS <= declarados, ALVOS_NOVOS - declarados
    linha_phony = next(x for x in texto.splitlines() if x.startswith(".PHONY"))
    for alvo in ALVOS_NOVOS:
        assert alvo in linha_phony, alvo


def test_dockerfile_copia_os_dados():
    """Sem isto a imagem sobe sem CSV e sem base de conhecimento: o contexto de
    build é agent/, e data/ vive um nível acima."""
    docker = (RAIZ / "agent" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY ./data ./data" in docker


def test_agent_data_e_artefato_de_build_nao_versionado():
    gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "agent/data/" in gitignore


@pytest.fixture(scope="module")
def dry_run():
    script = RAIZ / "infra" / "scripts" / "deploy.sh"
    return subprocess.run(
        ["bash", str(script), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        env={
            "PATH": "/usr/bin:/bin",
            "PROJECT_ID": "proj-teste",
            "REGION": "southamerica-east1",
            "AGENT_ENGINE_ID": "engine-teste",
        },
    )


def test_dry_run_nao_falha_e_mostra_os_comandos(dry_run):
    assert dry_run.returncode == 0, dry_run.stderr
    saida = dry_run.stdout
    assert "gcloud run deploy" in saida
    assert "proj-teste" in saida
    assert "southamerica-east1" in saida


def test_dry_run_nao_expoe_o_servico_publicamente(dry_run):
    """Fase 7 do HANDOFF: sem acesso público se não for necessário."""
    assert "--no-allow-unauthenticated" in dry_run.stdout
    assert "--allow-unauthenticated" not in dry_run.stdout.replace(
        "--no-allow-unauthenticated", ""
    )


def test_dry_run_usa_service_account_dedicada_e_minima(dry_run):
    saida = dry_run.stdout
    assert "--service-account" in saida
    assert "roles/aiplatform.user" in saida
    assert "roles/owner" not in saida
    assert "roles/editor" not in saida


def test_dry_run_passa_o_modo_nuvem_e_o_data_dir(dry_run):
    saida = dry_run.stdout
    assert "GOOGLE_GENAI_USE_VERTEXAI=true" in saida
    assert "DATA_DIR=/code/data" in saida


def test_sem_project_id_recusa():
    script = RAIZ / "infra" / "scripts" / "deploy.sh"
    r = subprocess.run(
        ["bash", str(script), "--dry-run"],
        capture_output=True, text=True, cwd=RAIZ,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode != 0
    assert "PROJECT_ID" in (r.stderr + r.stdout)


def test_dry_run_concede_permissao_de_build_a_sa_padrao(dry_run):
    """Projeto GCP novo não dá papéis à SA padrão do Compute, e é ela que o
    Cloud Build usa em `run deploy --source`. Sem esta concessão o deploy falha
    com storage.objects.get negado — acontece em todo projeto novo."""
    saida = dry_run.stdout
    assert "compute@developer.gserviceaccount.com" in saida
    assert "roles/cloudbuild.builds.builder" in saida


def test_dry_run_e_idempotente_no_repositorio_do_artifact_registry(dry_run):
    """Duas execuções simultâneas quebravam na criação do repositório."""
    assert "artifacts repositories create" in dry_run.stdout


def test_deploy_usa_sessao_e_memoria_gerenciadas(dry_run):
    """InMemorySessionService é um dict no processo: com mais de uma instância,
    o turno 2 pode cair onde a sessão não existe. Em produção tem de ser
    serviço compartilhado."""
    saida = dry_run.stdout
    assert "GOOGLE_CLOUD_AGENT_ENGINE_ID" in saida
    assert "MEMORY_BACKEND=agent_engine" in saida


def test_deploy_nao_limita_a_uma_instancia(dry_run):
    """max-instances=1 mascararia o problema em vez de resolvê-lo."""
    assert "--max-instances=1" not in dry_run.stdout


def test_sem_agent_engine_id_recusa():
    """Um id padrão apontaria a sessão para o engine de OUTRO projeto — o do
    preparo — e falharia por permissão com um erro que não explica a causa.
    No projeto do evento o id é outro, e precisa ser explícito."""
    script = RAIZ / "infra" / "scripts" / "deploy.sh"
    r = subprocess.run(
        ["bash", str(script), "--dry-run"],
        capture_output=True, text=True, cwd=RAIZ,
        env={"PATH": "/usr/bin:/bin", "PROJECT_ID": "proj-teste"},
    )
    assert r.returncode != 0
    assert "AGENT_ENGINE_ID" in (r.stdout + r.stderr)
    assert "make agent-engine" in (r.stdout + r.stderr)


def test_dry_run_usa_o_engine_informado(dry_run):
    assert "GOOGLE_CLOUD_AGENT_ENGINE_ID=engine-teste" in dry_run.stdout


def _dry(**extra):
    script = RAIZ / "infra" / "scripts" / "deploy.sh"
    env = {
        "PATH": "/usr/bin:/bin",
        "PROJECT_ID": "proj-teste",
        "REGION": "southamerica-east1",
        "AGENT_ENGINE_ID": "engine-teste",
        **extra,
    }
    return subprocess.run(
        ["bash", str(script), "--dry-run"], capture_output=True, text=True, cwd=RAIZ, env=env
    ).stdout


def test_deploy_e_privado_por_padrao_sem_allusers():
    saida = _dry()
    assert "allUsers" not in saida


def test_public_1_reaplica_o_acesso_publico_depois_do_deploy():
    """--no-allow-unauthenticated remove um allUsers concedido antes, em todo
    deploy. Quem escolheu público perde a escolha sem aviso — aconteceu três
    vezes. PUBLIC=1 reaplica o binding DEPOIS do deploy, explicitamente."""
    saida = _dry(PUBLIC="1")
    assert "--no-allow-unauthenticated" in saida  # o deploy em si continua privado
    assert "add-iam-policy-binding" in saida
    assert "--member=allUsers" in saida
    assert "--role=roles/run.invoker" in saida
    # O passo 2 também usa add-iam-policy-binding (SA -> aiplatform.user);
    # o que precisa vir DEPOIS do deploy é o binding do allUsers, especificamente.
    assert saida.index("run deploy") < saida.index("--member=allUsers")


def test_managed_iam_0_nao_cria_sa_nem_altera_iam():
    """Projeto do evento: sem serviceAccountAdmin nem setIamPolicy. Os passos
    1, 2 e 4 abortariam o deploy. Com MANAGED_IAM=0 eles somem e a SA de
    execução é a existente, informada em RUNTIME_SA."""
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="123-compute@developer.gserviceaccount.com")
    assert "service-accounts create" not in saida
    assert "add-iam-policy-binding" not in saida
    assert "--service-account=123-compute@developer.gserviceaccount.com" in saida


def test_managed_iam_0_builda_para_o_repo_existente_e_deploya_por_imagem():
    """artifactregistry.writer permite push mas não criar repositório: o build
    vai para o repo já provisionado (guia: 'agentes') e o deploy usa --image."""
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y", REGION="us-central1", AR_REPO="agentes")
    assert "artifacts repositories create" not in saida
    assert "builds submit" in saida
    assert "us-central1-docker.pkg.dev/proj-teste/agentes/batalha-agentes" in saida
    assert "--image=us-central1-docker.pkg.dev/proj-teste/agentes/batalha-agentes" in saida
    assert "--source=" not in saida


def test_model_key_secret_injeta_a_chave_lida_no_deploy():
    """A SA não lê o Secret Manager; o USUÁRIO lê no deploy e injeta na revisão
    (padrão do guia). O valor nunca aparece no dry-run — só o nome do segredo."""
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y", MODEL_KEY_SECRET="gemini-api-key")
    assert "GOOGLE_GENAI_USE_VERTEXAI=false" in saida
    assert "GEMINI_API_KEY=" in saida
    assert "secrets versions access latest --secret=gemini-api-key" in saida


def test_sem_model_key_secret_continua_vertex():
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y")
    assert "GOOGLE_GENAI_USE_VERTEXAI=true" in saida
    assert "GEMINI_API_KEY=" not in saida


def test_max_instances_e_data_source_sao_parametros():
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y", MAX_INSTANCES="5", DATA_SOURCE="evento")
    assert "--max-instances=5" in saida
    assert "DATA_SOURCE=evento" in saida


def test_demo_customer_id_e_repassado():
    """No dado do evento FICT-0001 não existe: a semeadura avisa e toda tool
    recusa. O id de demonstração precisa ser parâmetro do deploy."""
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y", DEMO_CUSTOMER_ID="00108ccd-699c")
    assert "DEMO_CUSTOMER_ID=00108ccd-699c" in saida
    # O bug estava no Makefile, não no script: _dry() chama o script direto e
    # não pegaria. O alvo `deploy` precisa repassar a variável.
    makefile = (RAIZ / "Makefile").read_text(encoding="utf-8")
    alvo = makefile[makefile.index("\ndeploy:"):makefile.index("\nagent-engine:")]
    assert "DEMO_CUSTOMER_ID=$(DEMO_CUSTOMER_ID)" in alvo


def test_build_local_nao_usa_cloud_build():
    """Projeto do evento: não há bucket de staging e o usuário não pode criar
    (storage.objectAdmin não tem buckets.create). Cloud Build está fora, por
    builds submit ou por --source. BUILD=local faz docker build + push, que só
    precisa de artifactregistry.writer."""
    saida = _dry(MANAGED_IAM="0", RUNTIME_SA="x@y", BUILD="local", REGION="us-central1")
    assert "builds submit" not in saida
    assert "docker build --platform linux/amd64" in saida
    assert "docker push us-central1-docker.pkg.dev/proj-teste/agentes/batalha-agentes" in saida
    assert "--image=us-central1-docker.pkg.dev/proj-teste/agentes/batalha-agentes" in saida
