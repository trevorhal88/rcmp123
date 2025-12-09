from sqlmodel import SQLModel, create_engine

def init_db():
    engine = create_engine("sqlite:///./rcmp123.db")
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()