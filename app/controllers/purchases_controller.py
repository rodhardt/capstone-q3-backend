from flask import jsonify, request
from http import HTTPStatus
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import Forbidden, BadRequest, NotFound

from app.configs.database import db
from app.models.purchases_model import PurchaseModel
from app.models.purchases_products_model import PurchaseProductModel
from app.services.customers_services import check_if_employee
from app.services.pagination_services import serialize_pagination


@jwt_required()
def create_purchase():
    try:
        try:
            check_if_employee(get_jwt_identity())
            data = request.get_json()
            session = db.session

            products_list = PurchaseModel.check_products_list(data['products'])
            purchase = PurchaseModel()

            for product in products_list:
                PurchaseModel.check_product(product.get('product_id'))
                product['purchase_id'] = purchase.id

                purchase_product = PurchaseProductModel(**product)
                purchase.products.append(purchase_product)

                inventory = PurchaseModel.get_inventory(purchase_product.product_id)
                inventory.quantity = inventory.quantity + purchase_product.quantity
                inventory.value = inventory.value + purchase_product.value

                session.add(inventory)

            session.add(purchase)
            session.commit()

            return jsonify(purchase), HTTPStatus.CREATED

        except KeyError:
            raise BadRequest(description="request must contain a products list")

        except AttributeError:
            raise BadRequest(description="'products' field must be a list")

        except TypeError:
            raise BadRequest(description="product data either missing or invalid")

    except Forbidden as e:
        return jsonify({"msg": e.description}), e.code
    
    except BadRequest as e:
        return jsonify({"msg": e.description}), e.code

    except NotFound as e:
        return jsonify({"msg": e.description}), e.code

@jwt_required()
def get_purchases():
    try:
        check_if_employee(get_jwt_identity())
        session = db.session
        base_query = session.query(PurchaseModel)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 3, type=int)

        purchases = base_query.order_by(PurchaseModel.id).paginate(page, per_page)
        response = serialize_pagination(purchases, "purchases")

        return jsonify(response), HTTPStatus.OK

    except Forbidden as e:
        return jsonify({"msg": e.description}), e.code

    except NotFound:
        return jsonify({"msg": "page not found"}), HTTPStatus.NOT_FOUND

@jwt_required()
def get_purchase_by_id(purchase_id):
    try:
        check_if_employee(get_jwt_identity())
        session = db.session
        base_query = session.query(PurchaseModel)

        purchase = base_query.get(purchase_id)

        PurchaseModel.check_purchase(purchase)

        return jsonify(purchase), HTTPStatus.OK

    except Forbidden as e:
        return jsonify({"msg": e.description}), e.code

    except NotFound as e:
        return jsonify({"msg": e.description}), e.code

@jwt_required()
def delete_purchase(purchase_id):
    try:
        check_if_employee(get_jwt_identity())
        session = db.session
        purchase_query = session.query(PurchaseModel)
        pur_prod_query = session.query(PurchaseProductModel)

        purchase = purchase_query.get(purchase_id)

        PurchaseModel.check_purchase(purchase)

        for purchase_product in purchase.products:
            inventory = PurchaseModel.get_inventory(purchase_product.product_id)
            inventory.quantity = inventory.quantity - purchase_product.quantity
            inventory.value = inventory.value - purchase_product.value

            session.add(inventory)

        pur_prods = pur_prod_query.filter_by(purchase_id=purchase_id).all()

        for pur_prod in pur_prods:
            session.delete(pur_prod)

        session.delete(purchase)
        session.commit()

        return '', HTTPStatus.NO_CONTENT

    except Forbidden as e:
        return jsonify({"msg": e.description}), e.code
    
    except NotFound as e:
        return jsonify({"msg": e.description}), e.code