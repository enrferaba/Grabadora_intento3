from app.database import Base, get_engine

engine = get_engine()
print("Creando tablas...")
Base.metadata.create_all(bind=engine)
print("✅ Base de datos inicializada correctamente.")
