from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

private_key = ec.generate_private_key(ec.SECP384R1())
public_key = private_key.public_key()

pem_private_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption())

pem_public_key = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo)
from py_vapid import Vapid

vapid_keys = Vapid()
vapid_keys.generate_keys()

if __name__ == '__main__':
    print(f'VAPID public key: {pem_public_key.decode("utf-8")}')
    print(f'VAPID private key: {pem_private_key.decode("utf-8")}')