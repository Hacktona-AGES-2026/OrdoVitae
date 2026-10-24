PRAGMA user_version = 1;

CREATE TABLE procedimentos (
    procedimento_id TEXT PRIMARY KEY NOT NULL,
    procedimento TEXT,
    especialidade TEXT,
    porte TEXT,
    risco_cirurgico INTEGER,
    duracao_media_min INTEGER,
    necessita_uti TEXT
);

CREATE TABLE fila_cirurgica (
    solicitacao_id TEXT PRIMARY KEY NOT NULL,
    paciente_id TEXT,
    nome_paciente TEXT,
    sexo TEXT,
    idade INTEGER,
    municipio TEXT,
    uf TEXT,
    distancia_hospital_km INTEGER,
    procedimento_id TEXT NOT NULL,
    procedimento TEXT,
    especialidade TEXT,
    cid_principal TEXT,
    cid_descricao TEXT,
    cid_secundario TEXT,
    asa INTEGER,
    comorbidades TEXT,
    intensidade_dor_eva INTEGER,
    limitacao_funcional TEXT,
    justificativa_clinica TEXT,
    observacoes TEXT,
    data_entrada_fila TEXT,
    dias_em_fila INTEGER,
    prioridade_regulacao TEXT,
    data_ultima_revisao_prioridade TEXT,
    flag_oncologico TEXT,
    flag_diabetico TEXT,
    flag_piora_clinica TEXT,
    hba1c_ultima REAL,
    data_hba1c_ultima TEXT,
    avaliacao_pre_anestesica TEXT,
    exames_pre_op_validos TEXT,
    FOREIGN KEY (procedimento_id) REFERENCES procedimentos (procedimento_id)
);

CREATE TABLE eventos_clinicos (
    evento_id TEXT PRIMARY KEY NOT NULL,
    solicitacao_id TEXT,
    paciente_id TEXT,
    data_evento TEXT,
    tipo_evento TEXT,
    resultado TEXT,
    valor_numerico REAL,
    descricao TEXT,
    origem TEXT
);

CREATE TABLE referencias_swalis (
    classe TEXT PRIMARY KEY NOT NULL,
    descricao TEXT,
    prazo_maximo_dias INTEGER,
    exemplos TEXT
);

CREATE INDEX idx_fila_paciente ON fila_cirurgica (paciente_id);
CREATE INDEX idx_fila_procedimento ON fila_cirurgica (procedimento_id);
CREATE INDEX idx_fila_cid ON fila_cirurgica (cid_principal);
CREATE INDEX idx_fila_especialidade ON fila_cirurgica (especialidade);
CREATE INDEX idx_fila_data_entrada ON fila_cirurgica (data_entrada_fila);
CREATE INDEX idx_eventos_solicitacao_data
    ON eventos_clinicos (solicitacao_id, data_evento);
CREATE INDEX idx_eventos_tipo_data
    ON eventos_clinicos (tipo_evento, data_evento);
