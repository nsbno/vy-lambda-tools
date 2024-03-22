locals {
  application_name = "my_app"
}
module "party_flag" {
  source = "../../../modules/feature_flag"

  application_name = local.application_name

  flag_name = "party_time"
}

module "party_vip_flag" {
  source = "../../../modules/feature_flag"

  application_name = local.application_name
  flag_name        = "party_vip"
}