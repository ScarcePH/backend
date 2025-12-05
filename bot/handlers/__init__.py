from .idle import handle as idle
from .size import handle as awaiting_size
from .confirmation import handle as awaiting_confirmation
from .payment import handle_payment_method
from .verify_payment import handle as verify_payment
from .customer_name import handle as awaiting_customer_name
from .customer_address import handle as awaiting_customer_address
from .customer_phone import handle as awaiting_customer_phone
